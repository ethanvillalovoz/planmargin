"""Private Waymax evidence adapter for the matched-search coordinator."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import numpy as np

from planmargin import behavior_features
from planmargin import controller_comparison
from planmargin import empirical_support
from planmargin import family_validation
from planmargin import lead_braking
from planmargin import speed_mutation

RunnerFactory = Callable[
    [controller_comparison.ControllerSpec],
    controller_comparison.ControllerRunner,
]
MutationApplier = Callable[
    [Any, int, lead_braking.LeadBrakingMutationConfig],
    tuple[Any | None, lead_braking.LeadBrakingMutationResult],
]
FeatureExtractor = Callable[..., behavior_features.BehaviorFeatureResult]
SupportScorer = Callable[[dict[str, Any], list[float]], dict[str, Any]]
ControllerRecordBuilder = Callable[
    [Any, int, dict[str, Any], str | None], dict[str, Any]
]


class WaymaxEvaluatorAdapter:
    """Return raw Waymax evidence while preserving the frozen evaluation order."""

    def __init__(
        self,
        *,
        runner_factory: RunnerFactory = controller_comparison.ControllerRunner,
        mutation_applier: MutationApplier = lead_braking.apply_lead_braking_mutation,
        mutation_validator: speed_mutation.MutationValidator | None = None,
        feature_extractor: FeatureExtractor = behavior_features.extract_object_pair_features,
        support_scorer: SupportScorer = empirical_support.score_vector,
        controller_record_builder: ControllerRecordBuilder = (
            family_validation._controller_record
        ),
    ) -> None:
        self._runner_factory = runner_factory
        self._mutation_applier = mutation_applier
        self._mutation_validator = mutation_validator or speed_mutation.MutationValidator(
            require_mutated_object_valid_all_steps=False
        )
        self._feature_extractor = feature_extractor
        self._support_scorer = support_scorer
        self._controller_record_builder = controller_record_builder
        self._runners: dict[
            controller_comparison.ControllerSpec,
            controller_comparison.ControllerRunner,
        ] = {}
        self._attempt_count = 0
        self._events: list[dict[str, int | str]] = []

    @property
    def events(self) -> tuple[dict[str, int | str], ...]:
        """Expose aggregate-safe stage events for smoke-test ordering checks."""
        return tuple(dict(event) for event in self._events)

    def _record_event(self, attempt_index: int, stage: str) -> None:
        self._events.append({"attempt_index": attempt_index, "stage": stage})

    def _runner(
        self, spec: controller_comparison.ControllerSpec
    ) -> controller_comparison.ControllerRunner:
        if spec not in self._runners:
            self._runners[spec] = self._runner_factory(spec)
        return self._runners[spec]

    @staticmethod
    def _sdc_index(scenario: Any) -> int:
        indices = np.flatnonzero(
            np.asarray(scenario.object_metadata.is_sdc, dtype=bool)
        )
        if indices.size != 1:
            raise ValueError(f"Expected one SDC, found {indices.size}")
        return int(indices[0])

    def evaluate_original(
        self,
        scenario: Any,
        candidate: dict[str, Any],
        tested: controller_comparison.ControllerSpec,
        reference: controller_comparison.ControllerSpec,
    ) -> dict[str, Any]:
        """Evaluate the unmodified scenario with both controller specifications."""
        object_index = candidate["interacting_object_index"]
        controllers = {}
        for role, spec in (("tested", tested), ("reference", reference)):
            rollout = self._runner(spec).run_twice(scenario)
            controllers[role] = self._controller_record_builder(
                scenario,
                object_index,
                rollout,
                None,
            )
        return {
            "eligible": all(
                record["outcome"]["success"] for record in controllers.values()
            ),
            "controllers": controllers,
        }

    def evaluate_attempt(
        self,
        scenario: Any,
        candidate: dict[str, Any],
        parameters: dict[str, float],
        tested: controller_comparison.ControllerSpec,
        reference: controller_comparison.ControllerSpec,
        support_model: dict[str, Any],
        original: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate one mutation and return only raw attempt and feature evidence."""
        attempt_index = self._attempt_count
        self._attempt_count += 1
        started = time.perf_counter()
        config = lead_braking.LeadBrakingMutationConfig(
            braking_onset_offset_s=parameters["braking_onset_offset_s"],
            speed_multiplier=parameters["speed_multiplier"],
        )
        object_index = candidate["interacting_object_index"]
        mutated_scenario, mutation = self._mutation_applier(
            scenario, object_index, config
        )
        self._record_event(attempt_index, "mutation")
        mutation_record = mutation.report(config)
        mutation_record["parameters"] = dict(parameters)
        attempt: dict[str, Any] = {
            "parameters": parameters,
            "identity_control": family_validation.is_identity_point(
                parameters["braking_onset_offset_s"],
                parameters["speed_multiplier"],
            ),
            "mutation": mutation_record,
            "status": "mutation_rejected",
            "scenario_validation": None,
            "controllers": None,
        }
        if mutated_scenario is None:
            attempt["elapsed_seconds"] = round(time.perf_counter() - started, 6)
            return {"attempt": attempt, "feature": None}

        validation = self._mutation_validator.validate(
            mutated_scenario, object_index
        )
        self._record_event(attempt_index, "scenario_validation")
        attempt["scenario_validation"] = validation
        if not validation["accepted"]:
            attempt["status"] = "scenario_rejected"
            attempt["elapsed_seconds"] = round(time.perf_counter() - started, 6)
            return {"attempt": attempt, "feature": None}

        trajectory = mutated_scenario.log_trajectory
        feature_result = self._feature_extractor(
            x=np.asarray(trajectory.x),
            y=np.asarray(trajectory.y),
            yaw=np.asarray(trajectory.yaw),
            vel_x=np.asarray(trajectory.vel_x),
            vel_y=np.asarray(trajectory.vel_y),
            valid=np.asarray(trajectory.valid),
            sdc_object_index=self._sdc_index(mutated_scenario),
            lead_object_index=object_index,
            current_timestep=speed_mutation.CURRENT_TIMESTEP,
        )
        feature = feature_result.report()
        self._record_event(attempt_index, "feature_extraction")
        if feature_result.accepted:
            assert feature_result.vector is not None
            self._support_scorer(support_model, list(feature_result.vector))
            self._record_event(attempt_index, "support_scoring")
        else:
            self._record_event(attempt_index, "support_unavailable")

        controllers = {}
        for role, spec in (("tested", tested), ("reference", reference)):
            self._record_event(attempt_index, f"{role}_controller")
            rollout = self._runner(spec).run_twice(mutated_scenario)
            controllers[role] = self._controller_record_builder(
                mutated_scenario,
                object_index,
                rollout,
                original["controllers"][role]["trajectory_sha256"],
            )
        attempt["controllers"] = controllers
        attempt["status"] = "accepted"
        attempt["elapsed_seconds"] = round(time.perf_counter() - started, 6)
        return {"attempt": attempt, "feature": feature}
