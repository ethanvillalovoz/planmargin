"""Data-free proposal core for the frozen matched-search comparison."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import warnings
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable, Literal, Sequence

import botorch
import gpytorch
import linear_operator
import numpy as np
import torch
from botorch.acquisition.multi_objective.logei import (
    qLogNoisyExpectedHypervolumeImprovement,
)
from botorch.acquisition.multi_objective.objective import (
    GenericMCMultiOutputObjective,
)
from botorch.fit import fit_gpytorch_mll
from botorch.models import ModelListGP, SingleTaskGP
from botorch.models.transforms.outcome import Standardize
from botorch.optim import optimize_acqf_mixed
from botorch.sampling.normal import SobolQMCNormalSampler
from gpytorch.mlls import SumMarginalLogLikelihood

SCHEMA_VERSION = "1.0.0"
METHODS = ("random", "bayesian")
TRACKS = ("natural", "headway_regression")
SEEDS = (0, 1, 2, 3, 4)
ONSET_OFFSETS_S = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
MINIMUM_SPEED_MULTIPLIER = 0.75
MAXIMUM_SPEED_MULTIPLIER = 1.0
PROPOSAL_BUDGET = 32
SOBOL_INITIALIZATION_COUNT = 8
OBSERVATION_VARIANCE = 1e-6
QMC_SAMPLES = 128
OPTIMIZER_RESTARTS = 10
OPTIMIZER_RAW_SAMPLES = 256
OPTIMIZER_MAX_ITERATIONS = 200
ACQUISITION_TIE_TOLERANCE = 1e-12
REFERENCE_POINT = (0.0, 0.0)
SUPPORT_ALPHA = 0.05
TORCH_DTYPE = torch.float64
TORCH_DEVICE = torch.device("cpu")

Method = Literal["random", "bayesian"]
Track = Literal["natural", "headway_regression"]


@dataclass(frozen=True)
class MatchedSearchConfig:
    """Immutable public configuration shared by both methods and tracks."""

    methods: tuple[str, ...] = METHODS
    tracks: tuple[str, ...] = TRACKS
    seeds: tuple[int, ...] = SEEDS
    proposal_budget: int = PROPOSAL_BUDGET
    sobol_initialization_count: int = SOBOL_INITIALIZATION_COUNT
    onset_offsets_s: tuple[float, ...] = ONSET_OFFSETS_S
    minimum_speed_multiplier: float = MINIMUM_SPEED_MULTIPLIER
    maximum_speed_multiplier: float = MAXIMUM_SPEED_MULTIPLIER
    numeric_dtype: str = "float64"
    device: str = "cpu"
    acquisition: str = "qLogNoisyExpectedHypervolumeImprovement"
    q: int = 1
    independent_exact_gp_outputs: int = 5
    objective_outputs: int = 2
    outcome_constraints: int = 3
    observation_variance: float = OBSERVATION_VARIANCE
    qmc_samples: int = QMC_SAMPLES
    optimizer_restarts: int = OPTIMIZER_RESTARTS
    optimizer_raw_samples: int = OPTIMIZER_RAW_SAMPLES
    optimizer_max_iterations: int = OPTIMIZER_MAX_ITERATIONS
    acquisition_tie_tolerance: float = ACQUISITION_TIE_TOLERANCE
    reference_point: tuple[float, float] = REFERENCE_POINT

    def validate(self) -> None:
        if self != MatchedSearchConfig():
            raise ValueError(
                "Matched-search configuration violates the frozen protocol"
            )


@dataclass(frozen=True)
class OutcomeRecord:
    """Method-neutral model outputs for one evaluated parameter pair."""

    parameters: tuple[float, float]
    objectives: tuple[float, float]
    constraints: tuple[float, float, float]
    objective_available: bool

    def model_outputs(self) -> tuple[float, ...]:
        values = (*self.objectives, *self.constraints)
        if (
            len(values) != 5
            or not np.isfinite(np.asarray(values, dtype=np.float64)).all()
        ):
            raise ValueError("Outcome record must contain five finite outputs")
        return values


@dataclass(frozen=True)
class ProposalDecision:
    """One deterministic proposal plus auditable optimizer diagnostics."""

    proposal_index: int
    parameters: tuple[float, float]
    source: str
    fallback_reason: str | None = None
    diagnostics: dict[str, Any] | None = None

    def report(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "proposal_index": self.proposal_index,
            "parameters": {
                "braking_onset_offset_s": self.parameters[0],
                "speed_multiplier": self.parameters[1],
            },
            "source": self.source,
            "fallback_reason": self.fallback_reason,
            "diagnostics": self.diagnostics,
        }


class BayesianOptimizationFailure(RuntimeError):
    """Identify the failed numerical stage while preserving its root cause."""

    def __init__(self, stage: str, cause: Exception) -> None:
        self.stage = stage
        self.cause_type = type(cause).__name__
        self.cause_message = str(cause)
        super().__init__(f"{stage}: {self.cause_type}: {self.cause_message}")


def dependency_report() -> dict[str, Any]:
    """Return the exact optimizer stack and enforced numerical device."""
    return {
        "python_api": SCHEMA_VERSION,
        "torch": torch.__version__,
        "botorch": botorch.__version__,
        "gpytorch": gpytorch.__version__,
        "linear_operator": linear_operator.__version__,
        "device": str(TORCH_DEVICE),
        "dtype": str(TORCH_DTYPE).removeprefix("torch."),
        "cuda_used": False,
        "mps_used": False,
        "configuration": asdict(MatchedSearchConfig()),
    }


def normalized_mutation_distance(parameters: tuple[float, float]) -> float:
    """Return the frozen Euclidean distance from the identity mutation."""
    onset, multiplier = parameters
    _validate_parameters(parameters)
    return math.sqrt((onset / 0.5) ** 2 + ((1.0 - multiplier) / 0.25) ** 2)


def evaluate_outcomes(
    *,
    parameters: tuple[float, float],
    minimum_signed_separation_m: float | None,
    pipeline_passes: bool,
    p_support: float | None,
    reference_succeeds: bool,
) -> OutcomeRecord:
    """Apply the frozen two-objective and three-constraint formulas."""
    _validate_parameters(parameters)
    if p_support is not None and (
        not math.isfinite(p_support) or not 0.0 <= p_support <= 1.0
    ):
        raise ValueError("p_support must be finite and within [0, 1]")
    if pipeline_passes and minimum_signed_separation_m is None:
        raise ValueError("pipeline-accepted outcomes require signed separation")
    objective_available = pipeline_passes and minimum_signed_separation_m is not None
    if objective_available:
        separation = float(minimum_signed_separation_m)
        if not math.isfinite(separation):
            raise ValueError("minimum signed separation must be finite")
        criticality = 1.0 / (1.0 + max(separation, 0.0))
        minimality = 1.0 - normalized_mutation_distance(parameters) / math.sqrt(2.0)
        objectives = (criticality, minimality)
    else:
        objectives = (0.0, 0.0)
    constraints = (
        -0.5 if pipeline_passes else 0.5,
        SUPPORT_ALPHA - p_support if p_support is not None else 1.0,
        -0.5 if reference_succeeds else 0.5,
    )
    record = OutcomeRecord(
        parameters=parameters,
        objectives=objectives,
        constraints=constraints,
        objective_available=objective_available,
    )
    record.model_outputs()
    return record


def _validate_indices(seed: int, selection_order: int, proposal_index: int) -> None:
    if seed not in SEEDS:
        raise ValueError("seed is outside the frozen set")
    if selection_order < 1:
        raise ValueError("selection_order must be positive")
    if not 0 <= proposal_index < PROPOSAL_BUDGET:
        raise ValueError("proposal_index is outside the frozen budget")


def _validate_parameters(parameters: tuple[float, float]) -> None:
    onset, multiplier = parameters
    if onset not in ONSET_OFFSETS_S:
        raise ValueError("braking onset is outside the frozen discrete set")
    if not math.isfinite(multiplier) or not (
        MINIMUM_SPEED_MULTIPLIER <= multiplier <= MAXIMUM_SPEED_MULTIPLIER
    ):
        raise ValueError("speed multiplier is outside the frozen bounds")


def random_parameters(
    *, seed: int, selection_order: int, proposal_index: int
) -> tuple[float, float]:
    """Return the version-two stateless PCG64 random-control proposal."""
    _validate_indices(seed, selection_order, proposal_index)
    generator = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([seed, selection_order, proposal_index]))
    )
    onset_index = int(generator.integers(0, len(ONSET_OFFSETS_S)))
    multiplier = MINIMUM_SPEED_MULTIPLIER + (
        MAXIMUM_SPEED_MULTIPLIER - MINIMUM_SPEED_MULTIPLIER
    ) * float(generator.random())
    parameters = (ONSET_OFFSETS_S[onset_index], multiplier)
    _validate_parameters(parameters)
    return parameters


def _stable_uint32(*parts: int | str) -> int:
    payload = json.dumps(parts, separators=(",", ":"), ensure_ascii=True).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def sobol_parameters(
    *, seed: int, selection_order: int, proposal_index: int
) -> tuple[float, float]:
    """Return a stateless point from the keyed scrambled Sobol sequence."""
    _validate_indices(seed, selection_order, proposal_index)
    engine = torch.quasirandom.SobolEngine(
        dimension=2,
        scramble=True,
        seed=_stable_uint32("sobol", seed, selection_order),
    )
    if proposal_index:
        engine.fast_forward(proposal_index)
    unit = engine.draw(1, dtype=TORCH_DTYPE)[0]
    onset_index = min(
        int(torch.floor(unit[0] * len(ONSET_OFFSETS_S)).item()),
        len(ONSET_OFFSETS_S) - 1,
    )
    multiplier = MINIMUM_SPEED_MULTIPLIER + (
        MAXIMUM_SPEED_MULTIPLIER - MINIMUM_SPEED_MULTIPLIER
    ) * float(unit[1].item())
    parameters = (ONSET_OFFSETS_S[onset_index], multiplier)
    _validate_parameters(parameters)
    return parameters


def acquisition_tie_digest(
    *,
    seed: int,
    selection_order: int,
    proposal_index: int,
    parameters: tuple[float, float],
) -> str:
    """Hash the frozen tie identity without a directional parameter preference."""
    _validate_indices(seed, selection_order, proposal_index)
    _validate_parameters(parameters)
    prefix = struct.pack(">qqq", seed, selection_order, proposal_index)
    onset_bytes = struct.pack(">d", parameters[0])
    speed_bytes = struct.pack(">d", parameters[1])
    return hashlib.sha256(prefix + onset_bytes + speed_bytes).hexdigest()


def resolve_acquisition_tie(
    *,
    seed: int,
    selection_order: int,
    proposal_index: int,
    candidates: Sequence[tuple[float, float]],
    acquisition_values: Sequence[float],
) -> int:
    """Return the winner, hashing all candidates within 1e-12 of the maximum."""
    if not candidates or len(candidates) != len(acquisition_values):
        raise ValueError("Candidate and acquisition lists must be non-empty and equal")
    values = np.asarray(acquisition_values, dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("Acquisition values must be finite")
    for candidate in candidates:
        _validate_parameters(candidate)
    maximum = float(np.max(values))
    tied = np.flatnonzero(
        np.isclose(values, maximum, rtol=0.0, atol=ACQUISITION_TIE_TOLERANCE)
    )
    return min(
        (int(index) for index in tied),
        key=lambda index: acquisition_tie_digest(
            seed=seed,
            selection_order=selection_order,
            proposal_index=proposal_index,
            parameters=candidates[index],
        ),
    )


def _torch_training_data(
    observations: Sequence[OutcomeRecord],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if len(observations) < 2:
        raise ValueError("At least two observations are required")
    train_x = torch.tensor(
        [observation.parameters for observation in observations],
        dtype=TORCH_DTYPE,
        device=TORCH_DEVICE,
    )
    train_y = torch.tensor(
        [observation.model_outputs() for observation in observations],
        dtype=TORCH_DTYPE,
        device=TORCH_DEVICE,
    )
    train_yvar = torch.full_like(train_y, OBSERVATION_VARIANCE)
    return train_x, train_y, train_yvar


def _fit_model(
    observations: Sequence[OutcomeRecord],
) -> tuple[ModelListGP, torch.Tensor]:
    train_x, train_y, train_yvar = _torch_training_data(observations)
    models = [
        SingleTaskGP(
            train_X=train_x,
            train_Y=train_y[:, output_index : output_index + 1],
            train_Yvar=train_yvar[:, output_index : output_index + 1],
            outcome_transform=Standardize(m=1),
        )
        for output_index in range(train_y.shape[-1])
    ]
    model = ModelListGP(*models)
    model.to(dtype=TORCH_DTYPE, device=TORCH_DEVICE)
    marginal_log_likelihood = SumMarginalLogLikelihood(model.likelihood, model)
    fit_gpytorch_mll(marginal_log_likelihood)
    model.eval()
    return model, train_x


def _build_acquisition(
    *,
    model: ModelListGP,
    train_x: torch.Tensor,
    seed: int,
    selection_order: int,
    proposal_index: int,
) -> qLogNoisyExpectedHypervolumeImprovement:
    """Construct the frozen two-objective, three-constraint qLogNEHVI."""
    objective = GenericMCMultiOutputObjective(lambda samples, X=None: samples[..., :2])
    constraints = [
        (lambda output_index: lambda samples: samples[..., output_index])(output_index)
        for output_index in (2, 3, 4)
    ]
    sampler = SobolQMCNormalSampler(
        sample_shape=torch.Size([QMC_SAMPLES]),
        seed=_stable_uint32("qmc", seed, selection_order, proposal_index),
    )
    return qLogNoisyExpectedHypervolumeImprovement(
        model=model,
        ref_point=list(REFERENCE_POINT),
        X_baseline=train_x,
        sampler=sampler,
        objective=objective,
        constraints=constraints,
        prune_baseline=False,
    )


def _model_fingerprint(model: ModelListGP) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        array = np.ascontiguousarray(tensor.detach().cpu().numpy())
        digest.update(name.encode())
        digest.update(str(array.dtype).encode())
        digest.update(str(array.shape).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def _optimize_bayesian(
    *,
    seed: int,
    selection_order: int,
    proposal_index: int,
    observations: Sequence[OutcomeRecord],
) -> tuple[tuple[float, float], dict[str, Any]]:
    if sum(observation.objective_available for observation in observations) < 2:
        raise ValueError("insufficient_accepted_objectives")
    torch.manual_seed(_stable_uint32("model", seed, selection_order, proposal_index))
    torch.use_deterministic_algorithms(True)
    try:
        with warnings.catch_warnings(record=True) as model_warnings:
            warnings.simplefilter("always")
            model, train_x = _fit_model(observations)
    except Exception as error:
        raise BayesianOptimizationFailure("model_fit", error) from error
    try:
        acquisition = _build_acquisition(
            model=model,
            train_x=train_x,
            seed=seed,
            selection_order=selection_order,
            proposal_index=proposal_index,
        )
    except Exception as error:
        raise BayesianOptimizationFailure("acquisition_construction", error) from error
    bounds = torch.tensor(
        [
            [min(ONSET_OFFSETS_S), MINIMUM_SPEED_MULTIPLIER],
            [max(ONSET_OFFSETS_S), MAXIMUM_SPEED_MULTIPLIER],
        ],
        dtype=TORCH_DTYPE,
        device=TORCH_DEVICE,
    )
    candidates: list[tuple[float, float]] = []
    acquisition_values: list[float] = []
    warning_messages = [str(item.message) for item in model_warnings]
    for onset_index, onset in enumerate(ONSET_OFFSETS_S):
        torch.manual_seed(
            _stable_uint32(
                "optimizer", seed, selection_order, proposal_index, onset_index
            )
        )
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                candidate, value = optimize_acqf_mixed(
                    acq_function=acquisition,
                    bounds=bounds,
                    q=1,
                    num_restarts=OPTIMIZER_RESTARTS,
                    fixed_features_list=[{0: onset}],
                    raw_samples=OPTIMIZER_RAW_SAMPLES,
                    options={"maxiter": OPTIMIZER_MAX_ITERATIONS},
                    retry_on_optimization_warning=False,
                )
        except Exception as error:
            raise BayesianOptimizationFailure(
                f"mixed_optimization_onset_{onset_index}", error
            ) from error
        warning_messages.extend(str(item.message) for item in caught)
        parameter_pair = (onset, float(candidate[0, 1].detach().cpu().item()))
        _validate_parameters(parameter_pair)
        scalar_value = float(value.detach().cpu().item())
        if not math.isfinite(scalar_value):
            raise BayesianOptimizationFailure(
                f"acquisition_value_onset_{onset_index}",
                ValueError("nonfinite_acquisition"),
            )
        candidates.append(parameter_pair)
        acquisition_values.append(scalar_value)
    winner = resolve_acquisition_tie(
        seed=seed,
        selection_order=selection_order,
        proposal_index=proposal_index,
        candidates=candidates,
        acquisition_values=acquisition_values,
    )
    return candidates[winner], {
        "model_fingerprint": _model_fingerprint(model),
        "training_observation_count": len(observations),
        "accepted_objective_count": sum(
            observation.objective_available for observation in observations
        ),
        "candidate_count": len(candidates),
        "acquisition_value": acquisition_values[winner],
        "warning_count": len(warning_messages),
        "warnings": warning_messages,
        "device": str(train_x.device),
        "dtype": str(train_x.dtype).removeprefix("torch."),
    }


BayesianOptimizer = Callable[
    [int, int, int, Sequence[OutcomeRecord]],
    tuple[tuple[float, float], dict[str, Any]],
]


def bayesian_proposal(
    *,
    seed: int,
    selection_order: int,
    proposal_index: int,
    observations: Sequence[OutcomeRecord],
    optimizer: BayesianOptimizer | None = None,
) -> ProposalDecision:
    """Return Sobol initialization, qLogNEHVI, or the frozen Sobol fallback."""
    _validate_indices(seed, selection_order, proposal_index)
    if len(observations) != proposal_index:
        raise ValueError("Bayesian observations must match the proposal index")
    if proposal_index < SOBOL_INITIALIZATION_COUNT:
        return ProposalDecision(
            proposal_index=proposal_index,
            parameters=sobol_parameters(
                seed=seed,
                selection_order=selection_order,
                proposal_index=proposal_index,
            ),
            source="sobol_initialization",
        )
    fallback = sobol_parameters(
        seed=seed,
        selection_order=selection_order,
        proposal_index=proposal_index,
    )
    if sum(observation.objective_available for observation in observations) < 2:
        return ProposalDecision(
            proposal_index=proposal_index,
            parameters=fallback,
            source="sobol_fallback",
            fallback_reason="insufficient_accepted_objectives",
            diagnostics={
                "failure_stage": "precondition",
                "failure_type": "InsufficientAcceptedObjectives",
                "failure_message": "fewer than two accepted objective observations",
                "accepted_objective_count": sum(
                    observation.objective_available for observation in observations
                ),
                "device": str(TORCH_DEVICE),
                "dtype": str(TORCH_DTYPE).removeprefix("torch."),
            },
        )
    selected_optimizer = optimizer
    if selected_optimizer is None:

        def selected_optimizer(
            optimizer_seed: int,
            optimizer_selection_order: int,
            optimizer_proposal_index: int,
            optimizer_observations: Sequence[OutcomeRecord],
        ) -> tuple[tuple[float, float], dict[str, Any]]:
            return _optimize_bayesian(
                seed=optimizer_seed,
                selection_order=optimizer_selection_order,
                proposal_index=optimizer_proposal_index,
                observations=optimizer_observations,
            )

    try:
        parameters, diagnostics = selected_optimizer(
            seed, selection_order, proposal_index, observations
        )
        _validate_parameters(parameters)
        return ProposalDecision(
            proposal_index=proposal_index,
            parameters=parameters,
            source="qlognehvi_mixed",
            diagnostics=diagnostics,
        )
    except Exception as error:  # The frozen fallback applies to every failure class.
        if isinstance(error, BayesianOptimizationFailure):
            failure_stage = error.stage
            failure_type = error.cause_type
            failure_message = error.cause_message
        else:
            failure_stage = "optimizer_callback"
            failure_type = type(error).__name__
            failure_message = str(error)
        return ProposalDecision(
            proposal_index=proposal_index,
            parameters=fallback,
            source="sobol_fallback",
            fallback_reason=f"{type(error).__name__}: {error}",
            diagnostics={
                "failure_stage": failure_stage,
                "failure_type": failure_type,
                "failure_message": failure_message,
                "accepted_objective_count": sum(
                    observation.objective_available for observation in observations
                ),
                "device": str(TORCH_DEVICE),
                "dtype": str(TORCH_DTYPE).removeprefix("torch."),
            },
        )


def synthetic_outcome(parameters: tuple[float, float]) -> OutcomeRecord:
    """Return a smooth, deterministic fixture that exercises all five outputs."""
    onset, multiplier = parameters
    _validate_parameters(parameters)
    separation = max(
        -0.1,
        1.1 - 1.4 * (onset / 0.5) - 1.1 * ((1.0 - multiplier) / 0.25),
    )
    p_support = min(
        0.99,
        max(0.01, 0.95 - 0.45 * (onset / 0.5) - 0.35 * ((1.0 - multiplier) / 0.25)),
    )
    reference_succeeds = separation > -0.05
    return evaluate_outcomes(
        parameters=parameters,
        minimum_signed_separation_m=separation,
        pipeline_passes=True,
        p_support=p_support,
        reference_succeeds=reference_succeeds,
    )


def run_synthetic_loop(
    *,
    seed: int,
    selection_order: int,
    optimizer: BayesianOptimizer | None = None,
) -> list[ProposalDecision]:
    """Exercise the complete 32-proposal state transition without private data."""
    decisions: list[ProposalDecision] = []
    observations: list[OutcomeRecord] = []
    for proposal_index in range(PROPOSAL_BUDGET):
        decision = bayesian_proposal(
            seed=seed,
            selection_order=selection_order,
            proposal_index=proposal_index,
            observations=observations,
            optimizer=optimizer,
        )
        decisions.append(decision)
        observations.append(synthetic_outcome(decision.parameters))
    return decisions


def proposals_report(decisions: Iterable[ProposalDecision]) -> str:
    """Return strict canonical JSON for fresh-process reproducibility tests."""
    return json.dumps(
        [decision.report() for decision in decisions],
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def main() -> None:
    """Print the public dependency and deterministic-environment report."""
    print(
        json.dumps(
            dependency_report(),
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
    )
