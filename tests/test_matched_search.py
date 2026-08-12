"""Data-free checks for the frozen matched-search proposal core."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import botorch
import gpytorch
import linear_operator
import pytest
import torch
from botorch.acquisition.multi_objective.logei import (
    qLogNoisyExpectedHypervolumeImprovement,
)
from botorch.models import ModelListGP, SingleTaskGP

from planmargin import matched_search
from planmargin import random_search


REPOSITORY_ROOT = Path(__file__).parents[1]


def _initial_observations(
    *, seed: int = 0, selection_order: int = 1
) -> list[matched_search.OutcomeRecord]:
    return [
        matched_search.synthetic_outcome(
            matched_search.sobol_parameters(
                seed=seed,
                selection_order=selection_order,
                proposal_index=index,
            )
        )
        for index in range(matched_search.SOBOL_INITIALIZATION_COUNT)
    ]


def _constant_optimizer(
    seed: int,
    selection_order: int,
    proposal_index: int,
    observations: list[matched_search.OutcomeRecord],
) -> tuple[tuple[float, float], dict[str, int]]:
    del seed, selection_order, observations
    return (0.2, 0.8), {"proposal_index": proposal_index}


def test_exact_configuration_dependency_stack_and_cpu_float64() -> None:
    config = matched_search.MatchedSearchConfig()
    config.validate()

    assert config.methods == ("random", "bayesian")
    assert config.tracks == ("natural", "headway_regression")
    assert config.seeds == (0, 1, 2, 3, 4)
    assert config.proposal_budget == 32
    assert config.sobol_initialization_count == 8
    assert config.onset_offsets_s == (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
    assert (config.minimum_speed_multiplier, config.maximum_speed_multiplier) == (
        0.75,
        1.0,
    )
    assert (
        config.independent_exact_gp_outputs,
        config.objective_outputs,
        config.outcome_constraints,
    ) == (5, 2, 3)
    assert (config.qmc_samples, config.optimizer_restarts) == (128, 10)
    assert (config.optimizer_raw_samples, config.optimizer_max_iterations) == (
        256,
        200,
    )

    report = matched_search.dependency_report()
    assert report["python_api"] == "1.0.0"
    assert report["torch"] == torch.__version__ == "2.13.0"
    assert report["botorch"] == botorch.__version__ == "0.18.1"
    assert report["gpytorch"] == gpytorch.__version__ == "1.15.2"
    assert report["linear_operator"] == linear_operator.__version__ == "0.6.1"
    assert report["device"] == "cpu"
    assert report["dtype"] == "float64"
    assert report["cuda_used"] is False
    assert report["mps_used"] is False

    with pytest.raises(ValueError, match="frozen protocol"):
        matched_search.MatchedSearchConfig(qmc_samples=64).validate()


def test_all_sobol_initial_designs_reproduce_in_a_fresh_process() -> None:
    local = {
        str(seed): [
            matched_search.sobol_parameters(
                seed=seed,
                selection_order=3,
                proposal_index=index,
            )
            for index in range(8)
        ]
        for seed in matched_search.SEEDS
    }
    program = """
import json
from planmargin import matched_search
print(json.dumps({
    str(seed): [matched_search.sobol_parameters(
        seed=seed, selection_order=3, proposal_index=index
    ) for index in range(8)]
    for seed in matched_search.SEEDS
}, sort_keys=True, separators=(\",\", \":\")))
"""
    fresh = subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(fresh.stdout) == {
        seed: [list(parameters) for parameters in design]
        for seed, design in local.items()
    }
    assert all(
        parameters[0] in matched_search.ONSET_OFFSETS_S
        and 0.75 <= parameters[1] <= 1.0
        for design in local.values()
        for parameters in design
    )


def test_random_control_matches_the_preserved_version_one_sampler() -> None:
    for seed in matched_search.SEEDS:
        for selection_order in (1, 7, 10):
            for proposal_index in (0, 8, 31):
                expected = random_search.proposal_parameters(
                    random_search.RandomSearchConfig(seed=seed),
                    selection_order,
                    proposal_index,
                )
                actual = matched_search.random_parameters(
                    seed=seed,
                    selection_order=selection_order,
                    proposal_index=proposal_index,
                )
                assert actual == (
                    expected["braking_onset_offset_s"],
                    expected["speed_multiplier"],
                )


def test_objective_and_constraint_reference_calculations() -> None:
    identity = matched_search.evaluate_outcomes(
        parameters=(0.0, 1.0),
        minimum_signed_separation_m=1.0,
        pipeline_passes=True,
        p_support=0.10,
        reference_succeeds=True,
    )
    assert identity.objectives == pytest.approx((0.5, 1.0))
    assert identity.constraints == pytest.approx((-0.5, -0.05, -0.5))
    assert identity.objective_available is True

    maximum_mutation = matched_search.evaluate_outcomes(
        parameters=(0.5, 0.75),
        minimum_signed_separation_m=-0.1,
        pipeline_passes=True,
        p_support=0.05,
        reference_succeeds=False,
    )
    assert maximum_mutation.objectives == pytest.approx((1.0, 0.0))
    assert maximum_mutation.constraints == pytest.approx((-0.5, 0.0, 0.5))

    rejected = matched_search.evaluate_outcomes(
        parameters=(0.1, 0.9),
        minimum_signed_separation_m=0.0,
        pipeline_passes=False,
        p_support=None,
        reference_succeeds=False,
    )
    assert rejected.objectives == (0.0, 0.0)
    assert rejected.constraints == (0.5, 1.0, 0.5)
    assert rejected.objective_available is False

    with pytest.raises(ValueError, match="require signed separation"):
        matched_search.evaluate_outcomes(
            parameters=(0.1, 0.9),
            minimum_signed_separation_m=None,
            pipeline_passes=True,
            p_support=0.1,
            reference_succeeds=True,
        )


def test_ties_use_sha_digest_and_not_candidate_order() -> None:
    candidates = [(onset, 0.8) for onset in matched_search.ONSET_OFFSETS_S]
    expected = min(
        range(len(candidates)),
        key=lambda index: matched_search.acquisition_tie_digest(
            seed=0,
            selection_order=1,
            proposal_index=8,
            parameters=candidates[index],
        ),
    )
    tied = matched_search.resolve_acquisition_tie(
        seed=0,
        selection_order=1,
        proposal_index=8,
        candidates=candidates,
        acquisition_values=[1.0 + index * 1e-13 for index in range(6)],
    )
    unique_maximum = matched_search.resolve_acquisition_tie(
        seed=0,
        selection_order=1,
        proposal_index=8,
        candidates=candidates,
        acquisition_values=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0 + 2e-12],
    )

    assert tied == expected
    assert unique_maximum == 5


def test_sobol_fallback_is_stateless_across_failure_classes() -> None:
    observations = _initial_observations()

    def runtime_failure(*args):
        del args
        raise RuntimeError("optimizer failed")

    def arithmetic_failure(*args):
        del args
        raise ArithmeticError("non-finite acquisition")

    first = matched_search.bayesian_proposal(
        seed=0,
        selection_order=1,
        proposal_index=8,
        observations=observations,
        optimizer=runtime_failure,
    )
    second = matched_search.bayesian_proposal(
        seed=0,
        selection_order=1,
        proposal_index=8,
        observations=observations,
        optimizer=arithmetic_failure,
    )
    expected = matched_search.sobol_parameters(
        seed=0, selection_order=1, proposal_index=8
    )

    assert first.parameters == second.parameters == expected
    assert first.source == second.source == "sobol_fallback"
    assert first.fallback_reason == "RuntimeError: optimizer failed"
    assert second.fallback_reason == "ArithmeticError: non-finite acquisition"
    assert first.diagnostics == {
        "failure_stage": "optimizer_callback",
        "failure_type": "RuntimeError",
        "failure_message": "optimizer failed",
        "accepted_objective_count": 8,
        "device": "cpu",
        "dtype": "float64",
    }
    assert second.diagnostics["failure_type"] == "ArithmeticError"

    unavailable = [
        matched_search.evaluate_outcomes(
            parameters=matched_search.sobol_parameters(
                seed=0, selection_order=1, proposal_index=index
            ),
            minimum_signed_separation_m=None,
            pipeline_passes=False,
            p_support=None,
            reference_succeeds=False,
        )
        for index in range(8)
    ]
    insufficient = matched_search.bayesian_proposal(
        seed=0,
        selection_order=1,
        proposal_index=8,
        observations=unavailable,
    )
    assert insufficient.parameters == expected
    assert insufficient.fallback_reason == "insufficient_accepted_objectives"
    assert insufficient.diagnostics["failure_stage"] == "precondition"
    assert insufficient.diagnostics["accepted_objective_count"] == 0


def test_model_and_acquisition_have_five_outputs_two_objectives_three_constraints(
) -> None:
    observations = _initial_observations()
    with pytest.warns(Warning):
        model, train_x = matched_search._fit_model(observations)
    acquisition = matched_search._build_acquisition(
        model=model,
        train_x=train_x,
        seed=0,
        selection_order=1,
        proposal_index=8,
    )

    assert isinstance(model, ModelListGP)
    assert len(model.models) == 5
    assert all(isinstance(output, SingleTaskGP) for output in model.models)
    assert train_x.device.type == "cpu"
    assert train_x.dtype == torch.float64
    assert isinstance(acquisition, qLogNoisyExpectedHypervolumeImprovement)
    assert len(acquisition.constraints) == 3

    samples = torch.tensor(
        [[[[0.2, 0.3, -0.5, 0.0, 0.5]]]], dtype=torch.float64
    )
    assert torch.equal(acquisition.objective(samples), samples[..., :2])
    assert [constraint(samples).item() for constraint in acquisition.constraints] == [
        -0.5,
        0.0,
        0.5,
    ]


def test_real_qlognehvi_transition_uses_mixed_domain_on_cpu() -> None:
    decision = matched_search.bayesian_proposal(
        seed=0,
        selection_order=1,
        proposal_index=8,
        observations=_initial_observations(),
    )

    assert decision.source == "qlognehvi_mixed"
    assert decision.parameters[0] in matched_search.ONSET_OFFSETS_S
    assert 0.75 <= decision.parameters[1] <= 1.0
    assert decision.diagnostics is not None
    assert decision.diagnostics["candidate_count"] == 6
    assert decision.diagnostics["training_observation_count"] == 8
    assert decision.diagnostics["accepted_objective_count"] == 8
    assert decision.diagnostics["device"] == "cpu"
    assert decision.diagnostics["dtype"] == "float64"
    assert len(decision.diagnostics["model_fingerprint"]) == 64


def test_complete_synthetic_state_machine_retains_duplicates_and_reproduces() -> None:
    local = matched_search.run_synthetic_loop(
        seed=4,
        selection_order=10,
        optimizer=_constant_optimizer,
    )
    local_report = matched_search.proposals_report(local)
    program = """
from planmargin import matched_search
def optimizer(seed, selection_order, proposal_index, observations):
    del seed, selection_order, observations
    return (0.2, 0.8), {\"proposal_index\": proposal_index}
print(matched_search.proposals_report(matched_search.run_synthetic_loop(
    seed=4, selection_order=10, optimizer=optimizer
)))
"""
    fresh = subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert len(local) == 32
    assert local[-1].proposal_index == 31
    assert [decision.parameters for decision in local[8:]] == [(0.2, 0.8)] * 24
    assert all(decision.source == "qlognehvi_mixed" for decision in local[8:])
    assert fresh.stdout.strip() == local_report
