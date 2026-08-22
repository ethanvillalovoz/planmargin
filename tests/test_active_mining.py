import json
from pathlib import Path

import numpy as np
import pytest
import torch

from planmargin import active_mining


def _examples(count_per_scenario: int = 18) -> list[active_mining.RiskExample]:
    values: list[active_mining.RiskExample] = []
    for selection_order in range(1, 11):
        for index in range(count_per_scenario):
            onset = (index % 6) / 10
            multiplier = 0.75 + 0.25 * index / (count_per_scenario - 1)
            features = np.asarray(
                [
                    12 + selection_order,
                    index / 4,
                    9 + selection_order / 2,
                    2 + index / 10,
                    3 + index / 8,
                    1 + index / 20,
                    0.85,
                    2.5,
                    onset,
                    multiplier,
                    index / count_per_scenario,
                    0.6,
                ],
                dtype=np.float32,
            )
            target = 14.0 - 5.0 * onset + 8.0 * multiplier + selection_order / 5
            values.append(
                active_mining.RiskExample(
                    selection_order=selection_order,
                    parameters=(onset, multiplier),
                    features=features,
                    target=target,
                )
            )
    return values


def test_risk_ensemble_returns_ordered_bounds() -> None:
    mean = np.zeros(len(active_mining.FEATURE_NAMES), dtype=np.float32)
    scale = np.ones(len(active_mining.FEATURE_NAMES), dtype=np.float32)
    torch.manual_seed(1)
    members = [active_mining.RiskMLP(mean, scale, 8) for _ in range(3)]
    ensemble = active_mining.RiskEnsemble(members, 2.0)
    output = ensemble(torch.zeros((4, len(active_mining.FEATURE_NAMES))))
    assert output.shape == (4, 3)
    assert torch.all(output[:, 1] <= output[:, 0])
    assert torch.all(output[:, 0] <= output[:, 2])


def test_qualification_preserves_scenario_isolation() -> None:
    config = active_mining.ActiveRiskConfig(
        ensemble_members=2,
        hidden_width=12,
        epochs=8,
        random_repeats=16,
    )
    report = active_mining.qualify(_examples(), config)
    assert len(report["folds"]) == 10
    assert all(fold["scenario_overlap_count"] == 0 for fold in report["folds"])
    assert all(fold["train_scenario_count"] == 8 for fold in report["folds"])
    assert report["scenario_count"] == 10


def test_eligible_scenario_protocol_preserves_group_isolation() -> None:
    config = active_mining.ActiveRiskConfig(
        ensemble_members=2,
        hidden_width=12,
        epochs=8,
        random_repeats=16,
    )
    examples = [value for value in _examples() if value.selection_order != 9]
    report = active_mining.qualify_eligible_scenarios(examples, config)
    assert len(report["folds"]) == 9
    assert all(fold["scenario_overlap_count"] == 0 for fold in report["folds"])
    assert all(fold["train_scenario_count"] == 7 for fold in report["folds"])
    assert report["scenario_count"] == 9


def test_deployment_calibration_uses_last_eligible_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    examples = [
        value for value in _examples(3) if value.selection_order in {1, 2, 3}
    ]
    observed: dict[str, object] = {}

    def fake_train(
        train: list[active_mining.RiskExample],
        config: active_mining.ActiveRiskConfig,
        fold: int,
    ) -> list[active_mining.RiskMLP]:
        del config, fold
        observed["train_orders"] = {value.selection_order for value in train}
        return [
            active_mining.RiskMLP(
                np.zeros(len(active_mining.FEATURE_NAMES), dtype=np.float32),
                np.ones(len(active_mining.FEATURE_NAMES), dtype=np.float32),
                4,
            )
        ]

    monkeypatch.setattr(active_mining, "_train_members", fake_train)
    monkeypatch.setattr(
        active_mining,
        "_member_predictions",
        lambda models, values: np.zeros((len(values), len(models))),
    )

    ensemble = active_mining._deployment_ensemble(
        examples, active_mining.ActiveRiskConfig(ensemble_members=1)
    )

    assert observed["train_orders"] == {1, 2}
    assert len(ensemble.members) == 1


def test_public_report_excludes_fold_rows_and_scenario_identifiers() -> None:
    report = {
        "record_type": "planmargin.active_risk_qualification",
        "schema_version": "1.0.0",
        "experiment": "v5",
        "source": "real",
        "synthetic": False,
        "evaluation": "retrospective",
        "feature_names": list(active_mining.FEATURE_NAMES),
        "target": active_mining.TARGET_NAME,
        "claim_boundary": "bounded",
        "unique_example_count": 900,
        "scenario_count": 10,
        "aggregate": {"mean_spearman": 0.5},
        "gates": {"safe": True},
        "status": "qualification_go",
        "model_sha256": "a" * 64,
        "onnx_sha256": "b" * 64,
        "folds": [{"holdout_selection_order": 1}],
    }
    public = active_mining.public_report(report)
    serialized = json.dumps(public)
    assert "folds" not in public
    assert "scenario_id" not in serialized
    assert public["redistribution"] == "aggregate_only"
    expected = public.pop("report_sha256")
    assert expected == active_mining._sha256(active_mining._canonical_json(public))


def test_load_examples_requires_complete_campaign(tmp_path: Path) -> None:
    try:
        active_mining.load_examples(tmp_path)
    except ValueError as error:
        assert "3,200" in str(error)
    else:
        raise AssertionError("Incomplete campaigns must be rejected")
