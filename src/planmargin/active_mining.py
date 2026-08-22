"""Qualify a learned risk ranker on immutable real-WOMD campaign outcomes."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
from scipy.stats import spearmanr
from torch import nn

from planmargin import behavior_features
from planmargin import random_search

DEFAULT_CAMPAIGN = Path("artifacts/search-comparison/natural-development-v1")
DEFAULT_OUTPUT = Path("artifacts/experiment-v5/active-risk")
PUBLIC_REPORT = Path("experiments/active-risk-qualification-v1.json")
BUDGETS = (1, 4, 8, 16, 32)
FEATURE_NAMES = (
    *behavior_features.FEATURE_NAMES,
    "braking_onset_offset_s",
    "speed_multiplier",
    "normalized_mutation_distance",
    "empirical_support_probability",
)
TARGET_NAME = "tested_minimum_signed_separation_m"
ENSEMBLE_MEMBERS = 5
HIDDEN_WIDTH = 64
EPOCHS = 320
RANDOM_REPEATS = 512
BASE_SEED = 2029


@dataclass(frozen=True)
class RiskExample:
    selection_order: int
    parameters: tuple[float, float]
    features: np.ndarray
    target: float


@dataclass(frozen=True)
class ActiveRiskConfig:
    ensemble_members: int = ENSEMBLE_MEMBERS
    hidden_width: int = HIDDEN_WIDTH
    epochs: int = EPOCHS
    learning_rate: float = 2e-3
    weight_decay: float = 1e-5
    random_repeats: int = RANDOM_REPEATS
    seed: int = BASE_SEED


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _proposal_paths(campaign: Path) -> list[Path]:
    return sorted(campaign.glob("cells/*/seed-*/scenario-*/proposals/proposal-*.json"))


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def load_examples(campaign: Path = DEFAULT_CAMPAIGN) -> list[RiskExample]:
    """Load and deduplicate eligible proposal records without leaking outcomes."""
    paths = _proposal_paths(campaign)
    if len(paths) != 3_200:
        raise ValueError(f"Expected 3,200 campaign proposals, found {len(paths)}")
    grouped: dict[tuple[int, float, float], list[tuple[np.ndarray, float]]] = (
        defaultdict(list)
    )
    for path in paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        random_search._validate_seal(record, "record_sha256", path=path)
        attempt = record.get("attempt")
        feature = record.get("feature")
        support = record.get("support")
        if (
            not isinstance(attempt, dict)
            or attempt.get("status") != "accepted"
            or not isinstance(feature, dict)
            or feature.get("accepted") is not True
            or not isinstance(support, dict)
            or not isinstance(attempt.get("controllers"), dict)
        ):
            continue
        names = tuple(feature.get("feature_names", ()))
        if names != tuple(behavior_features.FEATURE_NAMES):
            raise ValueError(f"Unexpected behavior feature contract: {path}")
        vector = [
            _finite_number(value, "behavior feature") for value in feature["vector"]
        ]
        parameters = record["proposal"]["parameters"]
        onset = _finite_number(parameters["braking_onset_offset_s"], "onset")
        multiplier = _finite_number(parameters["speed_multiplier"], "multiplier")
        distance = _finite_number(
            record["proposal"]["normalized_mutation_distance"], "mutation distance"
        )
        support_probability = _finite_number(
            support["p_support"], "support probability"
        )
        tested = attempt["controllers"]["tested"]
        target = _finite_number(
            tested["interaction_metrics"]["minimum_signed_separation_m"], TARGET_NAME
        )
        selection_order = int(record["identity"]["selection_order"])
        features = np.asarray(
            [*vector, onset, multiplier, distance, support_probability],
            dtype=np.float32,
        )
        if features.shape != (len(FEATURE_NAMES),) or not np.isfinite(features).all():
            raise ValueError(f"Invalid active-risk feature vector: {path}")
        grouped[(selection_order, round(onset, 12), round(multiplier, 12))].append(
            (features, target)
        )

    examples: list[RiskExample] = []
    for (selection_order, onset, multiplier), values in sorted(grouped.items()):
        feature_rows = np.stack([value[0] for value in values])
        targets = np.asarray([value[1] for value in values], dtype=np.float64)
        if float(np.max(np.ptp(feature_rows, axis=0))) > 1e-5:
            raise ValueError(
                "Equivalent proposal parameters produced inconsistent inputs"
            )
        if float(np.ptp(targets)) > 1e-5:
            raise ValueError(
                "Deterministic equivalent proposals produced inconsistent targets"
            )
        examples.append(
            RiskExample(
                selection_order=selection_order,
                parameters=(onset, multiplier),
                features=feature_rows[0],
                target=float(targets.mean()),
            )
        )
    return examples


class RiskMLP(nn.Module):
    """Small TensorRT-friendly risk regressor with sealed normalization."""

    def __init__(
        self, feature_mean: np.ndarray, feature_scale: np.ndarray, hidden_width: int
    ) -> None:
        super().__init__()
        self.hidden_width = hidden_width
        self.register_buffer(
            "feature_mean", torch.as_tensor(feature_mean, dtype=torch.float32)
        )
        self.register_buffer(
            "feature_scale", torch.as_tensor(feature_scale, dtype=torch.float32)
        )
        self.network = nn.Sequential(
            nn.Linear(len(FEATURE_NAMES), hidden_width),
            nn.SiLU(),
            nn.Linear(hidden_width, hidden_width),
            nn.SiLU(),
            nn.Linear(hidden_width, 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        normalized = (features - self.feature_mean) / self.feature_scale
        return self.network(normalized).squeeze(-1)


class RiskEnsemble(nn.Module):
    """Exportable ensemble returning mean, calibrated lower, and upper bounds."""

    def __init__(self, members: Iterable[RiskMLP], calibration_scale: float) -> None:
        super().__init__()
        self.members = nn.ModuleList(tuple(members))
        self.register_buffer(
            "calibration_scale",
            torch.tensor(float(calibration_scale), dtype=torch.float32),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        predictions = torch.stack([member(features) for member in self.members], dim=1)
        mean = predictions.mean(dim=1)
        spread = predictions.std(dim=1, unbiased=False).clamp_min(1e-3)
        radius = spread * self.calibration_scale
        return torch.stack((mean, mean - radius, mean + radius), dim=1)


def _arrays(examples: Iterable[RiskExample]) -> tuple[np.ndarray, np.ndarray]:
    values = tuple(examples)
    if not values:
        raise ValueError("Active-risk split is empty")
    return (
        np.stack([value.features for value in values]).astype(np.float32),
        np.asarray([value.target for value in values], dtype=np.float32),
    )


def _train_members(
    examples: list[RiskExample], config: ActiveRiskConfig, fold: int
) -> list[RiskMLP]:
    features, targets = _arrays(examples)
    feature_mean = features.mean(axis=0).astype(np.float32)
    feature_scale = np.maximum(features.std(axis=0), 1e-4).astype(np.float32)
    target_tensor = torch.from_numpy(targets)
    models: list[RiskMLP] = []
    for member_index in range(config.ensemble_members):
        seed = config.seed + fold * 100 + member_index
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        bootstrap = rng.choice(len(features), size=len(features), replace=True)
        feature_tensor = torch.from_numpy(features[bootstrap])
        bootstrap_targets = target_tensor[torch.from_numpy(bootstrap)]
        model = RiskMLP(feature_mean, feature_scale, config.hidden_width)
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )
        model.train()
        for _ in range(config.epochs):
            prediction = model(feature_tensor)
            loss = torch.nn.functional.smooth_l1_loss(
                prediction, bootstrap_targets, beta=1.0
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
        model.eval()
        models.append(model)
    return models


def _member_predictions(
    models: list[RiskMLP], examples: list[RiskExample]
) -> np.ndarray:
    features, _ = _arrays(examples)
    tensor = torch.from_numpy(features)
    with torch.inference_mode():
        return np.stack([model(tensor).numpy() for model in models], axis=1)


def _calibration_scale(predictions: np.ndarray, targets: np.ndarray) -> float:
    mean = predictions.mean(axis=1)
    spread = np.maximum(predictions.std(axis=1), 1e-3)
    ratios = np.abs(targets - mean) / spread
    return max(1.0, float(np.quantile(ratios, 0.9, method="higher")))


def _ranking_metrics(
    examples: list[RiskExample], scores: np.ndarray, config: ActiveRiskConfig, fold: int
) -> dict[str, Any]:
    targets = np.asarray([value.target for value in examples], dtype=np.float64)
    learned_order = np.argsort(scores, kind="stable")
    heuristic_order = np.asarray(
        sorted(
            range(len(examples)),
            key=lambda index: (
                examples[index].parameters[1],
                -examples[index].parameters[0],
            ),
        )
    )
    rng = np.random.default_rng(config.seed + 10_000 + fold)
    random_curves = np.empty((config.random_repeats, len(BUDGETS)), dtype=np.float64)
    for repeat in range(config.random_repeats):
        order = rng.permutation(len(examples))
        for budget_index, budget in enumerate(BUDGETS):
            random_curves[repeat, budget_index] = float(
                targets[order[: min(budget, len(order))]].min()
            )

    def curve(order: np.ndarray) -> list[float]:
        return [
            round(float(targets[order[: min(budget, len(order))]].min()), 6)
            for budget in BUDGETS
        ]

    learned = curve(learned_order)
    heuristic = curve(heuristic_order)
    random_median = np.median(random_curves, axis=0)
    return {
        "candidate_count": len(examples),
        "budgets": list(BUDGETS),
        "learned_best_separation_m": learned,
        "physical_heuristic_best_separation_m": heuristic,
        "random_median_best_separation_m": [
            round(float(value), 6) for value in random_median
        ],
        "oracle_separation_m": round(float(targets.min()), 6),
        "budget_8_random_minus_learned_m": round(
            float(random_median[2] - learned[2]), 6
        ),
        "budget_8_learned_beats_random": bool(learned[2] <= random_median[2]),
    }


def _fold_report(
    examples: list[RiskExample],
    holdout: int,
    config: ActiveRiskConfig,
    calibration: int | None = None,
    fold_seed: int | None = None,
) -> dict[str, Any]:
    if calibration is None:
        calibration = 10 if holdout == 1 else holdout - 1
    train = [
        example
        for example in examples
        if example.selection_order not in {holdout, calibration}
    ]
    calibration_examples = [
        example for example in examples if example.selection_order == calibration
    ]
    test = [example for example in examples if example.selection_order == holdout]
    train_orders = {example.selection_order for example in train}
    if train_orders & {holdout, calibration} or holdout == calibration:
        raise RuntimeError("Scenario-level split leakage detected")
    models = _train_members(train, config, holdout if fold_seed is None else fold_seed)
    calibration_predictions = _member_predictions(models, calibration_examples)
    _, calibration_targets = _arrays(calibration_examples)
    scale = _calibration_scale(calibration_predictions, calibration_targets)
    predictions = _member_predictions(models, test)
    _, targets = _arrays(test)
    mean = predictions.mean(axis=1)
    spread = np.maximum(predictions.std(axis=1), 1e-3)
    lower = mean - scale * spread
    upper = mean + scale * spread
    correlation = spearmanr(mean, targets).statistic
    if not math.isfinite(float(correlation)):
        correlation = 0.0
    return {
        "holdout_selection_order": holdout,
        "calibration_selection_order": calibration,
        "train_scenario_count": len(train_orders),
        "train_example_count": len(train),
        "calibration_example_count": len(calibration_examples),
        "test_example_count": len(test),
        "scenario_overlap_count": 0,
        "rmse_m": round(float(np.sqrt(np.mean(np.square(mean - targets)))), 6),
        "mae_m": round(float(np.mean(np.abs(mean - targets))), 6),
        "spearman": round(float(correlation), 6),
        "calibration_scale": round(scale, 6),
        "interval_coverage": round(
            float(np.mean((targets >= lower) & (targets <= upper))), 6
        ),
        "ranking": _ranking_metrics(test, lower, config, holdout),
    }


def qualify_eligible_scenarios(
    examples: list[RiskExample], config: ActiveRiskConfig
) -> dict[str, Any]:
    """Run the Experiment-v6 grouped protocol over every eligible scenario."""
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))
    # The CPU-only network uses explicit per-member seeds and deterministic
    # operators. Avoid PyTorch's process-global deterministic switch here: on
    # CPU-only Linux wheels it imports the unused Triton stack and can crash
    # before training starts (pytorch/pytorch#149735).
    orders = sorted({example.selection_order for example in examples})
    if len(orders) < 3:
        raise ValueError("At least three eligible scenarios are required")
    folds = []
    for fold_index, holdout in enumerate(orders):
        calibration = orders[fold_index - 1]
        folds.append(
            _fold_report(
                examples,
                holdout,
                config,
                calibration=calibration,
                fold_seed=fold_index + 1,
            )
        )
    mean_spearman = float(np.mean([fold["spearman"] for fold in folds]))
    mean_advantage = float(
        np.mean([fold["ranking"]["budget_8_random_minus_learned_m"] for fold in folds])
    )
    wins = sum(fold["ranking"]["budget_8_learned_beats_random"] for fold in folds)
    coverage = float(
        np.average(
            [fold["interval_coverage"] for fold in folds],
            weights=[fold["test_example_count"] for fold in folds],
        )
    )
    gates = {
        "minimum_500_unique_examples": len(examples) >= 500,
        "at_least_9_eligible_scenarios": len(orders) >= 9,
        "zero_scenario_leakage": all(
            fold["scenario_overlap_count"] == 0 for fold in folds
        ),
        "mean_spearman_at_least_0_25": mean_spearman >= 0.25,
        "budget_8_advantage_at_least_0_25_m": mean_advantage >= 0.25,
        "budget_8_wins_at_least_7_scenarios": wins >= 7,
        "coverage_between_0_75_and_0_98": 0.75 <= coverage <= 0.98,
    }
    return {
        "unique_example_count": len(examples),
        "scenario_count": len(orders),
        "folds": folds,
        "aggregate": {
            "mean_spearman": round(mean_spearman, 6),
            "mean_budget_8_random_minus_learned_m": round(mean_advantage, 6),
            "budget_8_win_count": wins,
            "interval_coverage": round(coverage, 6),
        },
        "gates": gates,
        "status": "qualification_go" if all(gates.values()) else "qualification_no_go",
    }


def qualify(examples: list[RiskExample], config: ActiveRiskConfig) -> dict[str, Any]:
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))
    orders = sorted({example.selection_order for example in examples})
    if orders != list(range(1, 11)):
        counts = {
            str(order): sum(example.selection_order == order for example in examples)
            for order in range(1, 11)
        }
        gates = {
            "minimum_500_unique_examples": len(examples) >= 500,
            "exactly_10_scenarios": False,
            "zero_scenario_leakage": False,
            "mean_spearman_at_least_0_25": False,
            "budget_8_advantage_at_least_0_25_m": False,
            "budget_8_wins_at_least_7_scenarios": False,
            "coverage_between_0_75_and_0_98": False,
        }
        return {
            "unique_example_count": len(examples),
            "scenario_count": len(orders),
            "eligible_examples_by_selection_order": counts,
            "folds": [],
            "aggregate": None,
            "gates": gates,
            "status": "qualification_no_go",
            "stop_reason": "missing_eligible_scenario_targets",
        }
    folds = [_fold_report(examples, holdout, config) for holdout in orders]
    mean_spearman = float(np.mean([fold["spearman"] for fold in folds]))
    mean_advantage = float(
        np.mean([fold["ranking"]["budget_8_random_minus_learned_m"] for fold in folds])
    )
    wins = sum(fold["ranking"]["budget_8_learned_beats_random"] for fold in folds)
    coverage = float(
        np.average(
            [fold["interval_coverage"] for fold in folds],
            weights=[fold["test_example_count"] for fold in folds],
        )
    )
    gates = {
        "minimum_500_unique_examples": len(examples) >= 500,
        "exactly_10_scenarios": len(orders) == 10,
        "zero_scenario_leakage": all(
            fold["scenario_overlap_count"] == 0 for fold in folds
        ),
        "mean_spearman_at_least_0_25": mean_spearman >= 0.25,
        "budget_8_advantage_at_least_0_25_m": mean_advantage >= 0.25,
        "budget_8_wins_at_least_7_scenarios": wins >= 7,
        "coverage_between_0_75_and_0_98": 0.75 <= coverage <= 0.98,
    }
    return {
        "unique_example_count": len(examples),
        "scenario_count": len(orders),
        "folds": folds,
        "aggregate": {
            "mean_spearman": round(mean_spearman, 6),
            "mean_budget_8_random_minus_learned_m": round(mean_advantage, 6),
            "budget_8_win_count": wins,
            "interval_coverage": round(coverage, 6),
        },
        "gates": gates,
        "status": "qualification_go" if all(gates.values()) else "qualification_no_go",
    }


def _serialize_ensemble(ensemble: RiskEnsemble, config: ActiveRiskConfig) -> bytes:
    output = io.BytesIO()
    entries: dict[str, bytes] = {
        "configuration.json": _canonical_json(
            {
                "feature_names": list(FEATURE_NAMES),
                "target_name": TARGET_NAME,
                "hidden_width": config.hidden_width,
                "ensemble_members": config.ensemble_members,
                "calibration_scale": float(ensemble.calibration_scale),
            }
        )
    }
    for member_index, member in enumerate(ensemble.members):
        for name, tensor in sorted(member.state_dict().items()):
            payload = io.BytesIO()
            np.save(payload, tensor.detach().cpu().numpy(), allow_pickle=False)
            entries[f"member-{member_index:02d}-{name}.npy"] = payload.getvalue()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, entries[name])
    return output.getvalue()


def _deployment_ensemble(
    examples: list[RiskExample], config: ActiveRiskConfig
) -> RiskEnsemble:
    eligible_orders = sorted({example.selection_order for example in examples})
    if len(eligible_orders) < 2:
        raise ValueError("Deployment calibration requires at least two scenarios")
    calibration_order = eligible_orders[-1]
    train = [
        example for example in examples if example.selection_order != calibration_order
    ]
    calibration = [
        example for example in examples if example.selection_order == calibration_order
    ]
    members = _train_members(train, config, 99)
    calibration_predictions = _member_predictions(members, calibration)
    _, targets = _arrays(calibration)
    return RiskEnsemble(
        members, _calibration_scale(calibration_predictions, targets)
    ).eval()


def export_onnx(ensemble: RiskEnsemble, path: Path) -> Path:
    try:
        import onnx
    except ImportError as error:
        raise RuntimeError(
            "Install the 'nvidia' extra to export active-risk ONNX"
        ) from error
    path.parent.mkdir(parents=True, exist_ok=True)
    batch = torch.export.Dim("batch")
    torch.onnx.export(
        ensemble,
        (torch.zeros((2, len(FEATURE_NAMES)), dtype=torch.float32),),
        path,
        input_names=["candidate_features"],
        output_names=["risk_bounds_m"],
        dynamic_shapes=({0: batch},),
        opset_version=18,
        dynamo=True,
        external_data=False,
    )
    onnx.checker.check_model(onnx.load(path))
    return path


def run(
    campaign: Path = DEFAULT_CAMPAIGN,
    output: Path = DEFAULT_OUTPUT,
    config: ActiveRiskConfig = ActiveRiskConfig(),
) -> Path:
    examples = load_examples(campaign)
    result = qualify(examples, config)
    output.mkdir(parents=True, exist_ok=True)
    model_payload: bytes | None = None
    onnx_path: Path | None = None
    if result["status"] == "qualification_go":
        ensemble = _deployment_ensemble(examples, config)
        model_payload = _serialize_ensemble(ensemble, config)
        model_path = output / "active-risk-ensemble.pmrisk"
        model_path.write_bytes(model_payload)
        onnx_path = export_onnx(ensemble, output / "active-risk-ensemble.onnx")
    report: dict[str, Any] = {
        "record_type": "planmargin.active_risk_qualification",
        "schema_version": "1.0.0",
        "experiment": "v5",
        "source": "immutable natural-development-v1 real-WOMD Waymax outcomes",
        "synthetic": False,
        "evaluation": "retrospective scenario-held-out qualification",
        "configuration": asdict(config),
        "feature_names": list(FEATURE_NAMES),
        "prohibited_features": [
            "scenario_id",
            "method",
            "seed",
            "proposal_index",
            "controller_output",
            "trajectory_hash",
            "post_rollout_metric",
        ],
        "target": TARGET_NAME,
        "claim_boundary": (
            "Qualifies a learned ranker for prospective testing; does not claim a new "
            "planner failure or production-driving result."
        ),
        **result,
        "model_bytes": None if model_payload is None else len(model_payload),
        "model_sha256": None if model_payload is None else _sha256(model_payload),
        "onnx_bytes": None if onnx_path is None else onnx_path.stat().st_size,
        "onnx_sha256": None if onnx_path is None else _sha256(onnx_path.read_bytes()),
        "source_sha256": _sha256(Path(__file__).read_bytes()),
    }
    logical = {key: value for key, value in report.items() if key != "source_sha256"}
    report["logical_fingerprint"] = _sha256(_canonical_json(logical))
    report["report_sha256"] = _sha256(_canonical_json(report))
    report_path = output / "qualification-report.json"
    report_path.write_bytes(_canonical_json(report))
    return report_path


def run_v6(
    campaign: Path = DEFAULT_CAMPAIGN,
    output: Path = Path("artifacts/experiment-v6/active-risk"),
    config: ActiveRiskConfig = ActiveRiskConfig(),
) -> Path:
    examples = load_examples(campaign)
    result = qualify_eligible_scenarios(examples, config)
    output.mkdir(parents=True, exist_ok=True)
    model_payload: bytes | None = None
    onnx_path: Path | None = None
    if result["status"] == "qualification_go":
        ensemble = _deployment_ensemble(examples, config)
        model_payload = _serialize_ensemble(ensemble, config)
        (output / "active-risk-ensemble.pmrisk").write_bytes(model_payload)
        onnx_path = export_onnx(ensemble, output / "active-risk-ensemble.onnx")
    report: dict[str, Any] = {
        "record_type": "planmargin.active_risk_qualification",
        "schema_version": "1.0.0",
        "experiment": "v6",
        "source": "immutable natural-development-v1 real-WOMD Waymax outcomes",
        "synthetic": False,
        "evaluation": "retrospective eligible-scenario-held-out qualification",
        "configuration": asdict(config),
        "feature_names": list(FEATURE_NAMES),
        "prohibited_features": [
            "scenario_id",
            "method",
            "seed",
            "proposal_index",
            "controller_output",
            "trajectory_hash",
            "post_rollout_metric",
        ],
        "target": TARGET_NAME,
        "claim_boundary": (
            "Qualifies a learned ranker for prospective testing; does not claim a new "
            "planner failure or production-driving result."
        ),
        **result,
        "model_bytes": None if model_payload is None else len(model_payload),
        "model_sha256": None if model_payload is None else _sha256(model_payload),
        "onnx_bytes": None if onnx_path is None else onnx_path.stat().st_size,
        "onnx_sha256": None if onnx_path is None else _sha256(onnx_path.read_bytes()),
        "source_sha256": _sha256(Path(__file__).read_bytes()),
    }
    logical = {key: value for key, value in report.items() if key != "source_sha256"}
    report["logical_fingerprint"] = _sha256(_canonical_json(logical))
    report["report_sha256"] = _sha256(_canonical_json(report))
    report_path = output / "qualification-report.json"
    report_path.write_bytes(_canonical_json(report))
    return report_path


def public_report(report: dict[str, Any]) -> dict[str, Any]:
    """Return the aggregate-only tracked record."""
    public = {
        "record_type": report["record_type"],
        "schema_version": report["schema_version"],
        "experiment": report["experiment"],
        "source": report["source"],
        "synthetic": report["synthetic"],
        "evaluation": report["evaluation"],
        "feature_names": report["feature_names"],
        "target": report["target"],
        "claim_boundary": report["claim_boundary"],
        "unique_example_count": report["unique_example_count"],
        "scenario_count": report["scenario_count"],
        "aggregate": report["aggregate"],
        "gates": report["gates"],
        "status": report["status"],
        "stop_reason": report.get("stop_reason"),
        "model_sha256": report["model_sha256"],
        "onnx_sha256": report["onnx_sha256"],
        "redistribution": "aggregate_only",
    }
    public["report_sha256"] = _sha256(_canonical_json(public))
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--ensemble-members", type=int, default=ENSEMBLE_MEMBERS)
    parser.add_argument("--random-repeats", type=int, default=RANDOM_REPEATS)
    parser.add_argument("--public-report", type=Path)
    args = parser.parse_args()
    config = ActiveRiskConfig(
        epochs=args.epochs,
        ensemble_members=args.ensemble_members,
        random_repeats=args.random_repeats,
    )
    path = run(args.campaign, args.output, config)
    if args.public_report is not None:
        report = json.loads(path.read_text(encoding="utf-8"))
        args.public_report.parent.mkdir(parents=True, exist_ok=True)
        args.public_report.write_bytes(_canonical_json(public_report(report)))
    print(path)


def v6_main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/experiment-v6/active-risk")
    )
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--ensemble-members", type=int, default=ENSEMBLE_MEMBERS)
    parser.add_argument("--random-repeats", type=int, default=RANDOM_REPEATS)
    parser.add_argument("--public-report", type=Path)
    args = parser.parse_args()
    config = ActiveRiskConfig(
        epochs=args.epochs,
        ensemble_members=args.ensemble_members,
        random_repeats=args.random_repeats,
    )
    path = run_v6(args.campaign, args.output, config)
    if args.public_report is not None:
        report = json.loads(path.read_text(encoding="utf-8"))
        args.public_report.parent.mkdir(parents=True, exist_ok=True)
        args.public_report.write_bytes(_canonical_json(public_report(report)))
    print(path)


if __name__ == "__main__":
    main()
