"""Data-free tests for the private matched-search Waymax adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from planmargin import behavior_features
from planmargin import controller_comparison
from planmargin import matched_coordinator
from planmargin import matched_search
from planmargin import matched_smoke
from planmargin import matched_waymax


@dataclass
class _Mutation:
    accepted: bool = True

    def report(self, config: Any) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "mutation_type": "lead_braking_onset_and_speed",
            "accepted": self.accepted,
            "parameters": {
                "braking_onset_offset_s": config.braking_onset_offset_s,
                "speed_multiplier": config.speed_multiplier,
                "fixed_bound_from_underlying_mutation": 100.0,
            },
            "rejection_reasons": [] if self.accepted else ["rejected"],
            "metrics": {},
        }


class _Validator:
    def __init__(self, events: list[str], accepted: bool = True) -> None:
        self._events = events
        self._accepted = accepted

    def validate(self, scenario: Any, object_index: int) -> dict[str, Any]:
        del scenario, object_index
        self._events.append("scenario_validation")
        return {
            "accepted": self._accepted,
            "rejection_reasons": [] if self._accepted else ["rejected"],
            "outputs_identical": True,
            "trajectory_sha256": "validation",
        }


class _Runner:
    def __init__(self, role: str, events: list[str]) -> None:
        self._role = role
        self._events = events

    def run_twice(self, scenario: Any) -> dict[str, Any]:
        del scenario
        self._events.append(f"{self._role}_controller")
        return {"role": self._role}


def _scenario() -> Any:
    shape = (2, 91)
    trajectory = SimpleNamespace(
        x=np.zeros(shape),
        y=np.zeros(shape),
        yaw=np.zeros(shape),
        vel_x=np.zeros(shape),
        vel_y=np.zeros(shape),
        valid=np.ones(shape, dtype=bool),
    )
    return SimpleNamespace(
        log_trajectory=trajectory,
        object_metadata=SimpleNamespace(is_sdc=np.array([False, True])),
    )


def _controller_record(
    scenario: Any,
    object_index: int,
    rollout: dict[str, Any],
    original_hash: str | None,
) -> dict[str, Any]:
    del scenario, object_index, original_hash
    return {
        "outputs_identical": True,
        "trajectory_sha256": f"{rollout['role']}-hash",
        "changed_from_original": True,
        "outcome": {"success": True},
        "interaction_metrics": {"minimum_signed_separation_m": 1.0},
        "first_rollout_seconds": 0.1,
        "second_rollout_seconds": 0.1,
    }


def _adapter(
    events: list[str], *, feature_accepted: bool = True
) -> matched_waymax.WaymaxEvaluatorAdapter:
    scenario = _scenario()

    def apply_mutation(
        source: Any, object_index: int, config: Any
    ) -> tuple[Any, _Mutation]:
        del source, object_index, config
        events.append("mutation")
        return scenario, _Mutation()

    def extract_feature(**kwargs: Any) -> behavior_features.BehaviorFeatureResult:
        del kwargs
        events.append("feature_extraction")
        if not feature_accepted:
            return behavior_features.BehaviorFeatureResult(
                False,
                ("six_second_window_incomplete",),
                {},
                None,
            )
        return behavior_features.BehaviorFeatureResult(
            True,
            (),
            {
                **{name: float(index) for index, name in enumerate(behavior_features.FEATURE_NAMES)},
                "current_sdc_speed_mps": 10.0,
                "maximum_absolute_jerk_mps3": 2.0,
            },
            tuple(float(index) for index in range(len(behavior_features.FEATURE_NAMES))),
        )

    def score_support(
        model: dict[str, Any], vector: list[float]
    ) -> dict[str, Any]:
        del model, vector
        events.append("support_scoring")
        return {
            "nonconformity": 99.0,
            "p_support": 0.01,
            "constraint": 0.04,
            "passes": False,
            "tie_inclusive_calibration_count": 0,
        }

    return matched_waymax.WaymaxEvaluatorAdapter(
        runner_factory=lambda spec: _Runner(spec.role, events),
        mutation_applier=apply_mutation,
        mutation_validator=_Validator(events),
        feature_extractor=extract_feature,
        support_scorer=score_support,
        controller_record_builder=_controller_record,
    )


def _original() -> dict[str, Any]:
    return {
        "eligible": True,
        "controllers": {
            "tested": {"trajectory_sha256": "tested-original"},
            "reference": {"trajectory_sha256": "reference-original"},
        },
    }


def test_support_is_scored_before_both_controllers_even_when_it_fails() -> None:
    events: list[str] = []
    adapter = _adapter(events)
    result = adapter.evaluate_attempt(
        _scenario(),
        {"interacting_object_index": 0},
        {"braking_onset_offset_s": 0.3, "speed_multiplier": 0.8},
        controller_comparison.TESTED_CONTROLLER,
        controller_comparison.REFERENCE_CONTROLLER,
        {"validated": True},
        _original(),
    )

    assert events == [
        "mutation",
        "scenario_validation",
        "feature_extraction",
        "support_scoring",
        "tested_controller",
        "reference_controller",
    ]
    assert result["attempt"]["status"] == "accepted"
    assert result["attempt"]["mutation"]["parameters"] == {
        "braking_onset_offset_s": 0.3,
        "speed_multiplier": 0.8,
    }
    assert set(result["attempt"]["controllers"]) == {"tested", "reference"}
    assert set(result) == {"attempt", "feature"}
    assert tuple(event["stage"] for event in adapter.events) == tuple(events)


def test_feature_rejection_still_runs_both_controllers_without_scoring() -> None:
    events: list[str] = []
    adapter = _adapter(events, feature_accepted=False)
    result = adapter.evaluate_attempt(
        _scenario(),
        {"interacting_object_index": 0},
        {"braking_onset_offset_s": 0.4, "speed_multiplier": 0.8},
        controller_comparison.TESTED_CONTROLLER,
        controller_comparison.REFERENCE_CONTROLLER,
        {"validated": True},
        _original(),
    )

    assert events == [
        "mutation",
        "scenario_validation",
        "feature_extraction",
        "tested_controller",
        "reference_controller",
    ]
    assert tuple(event["stage"] for event in adapter.events) == (
        "mutation",
        "scenario_validation",
        "feature_extraction",
        "support_unavailable",
        "tested_controller",
        "reference_controller",
    )
    assert result["feature"]["accepted"] is False
    assert result["attempt"]["controllers"] is not None


def test_smoke_runner_freezes_scope_and_emits_only_aggregate_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    output = Path("artifacts/search-comparison/test-smoke")
    calls: list[dict[str, Any]] = []

    class Adapter:
        events = tuple(
            {"attempt_index": attempt, "stage": stage}
            for attempt in range(2)
            for stage in matched_smoke.EXPECTED_ATTEMPT_STAGES
        )

        @staticmethod
        def evaluate_original(*args: Any, **kwargs: Any) -> dict[str, Any]:
            del args, kwargs
            return {}

        @staticmethod
        def evaluate_attempt(*args: Any, **kwargs: Any) -> dict[str, Any]:
            del args, kwargs
            return {}

    def coordinator_run(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        if len(calls) == 1:
            output.mkdir(parents=True, exist_ok=True)
            (output / "original.json").write_text(
                json.dumps({"cost": {"total_physical_rollouts": 4}})
            )
            for index in range(2):
                parameters = matched_search.random_parameters(
                    seed=0, selection_order=1, proposal_index=index
                )
                selection_path = matched_coordinator._selection_path(output, index)
                proposal_path = matched_coordinator._proposal_path(output, index)
                selection_path.parent.mkdir(parents=True, exist_ok=True)
                proposal_path.parent.mkdir(parents=True, exist_ok=True)
                selection_path.write_text(
                    json.dumps({"selection_sha256": f"selection-{index}"})
                )
                proposal_path.write_text(
                    json.dumps(
                        {
                            "identity": {"proposal_index": index},
                            "selection_sha256": f"selection-{index}",
                            "proposal": {
                                "parameters": {
                                    "braking_onset_offset_s": parameters[0],
                                    "speed_multiplier": parameters[1],
                                }
                            },
                            "attempt": {
                                "status": "accepted",
                                "controllers": {"tested": {}, "reference": {}},
                            },
                            "feature": {"accepted": True},
                            "support": {"passes": index == 0},
                            "cost": {"total_physical_rollouts": 6},
                        }
                    )
                )
            return {
                "status": "in_progress",
                "completed_proposal_count": 2,
                "new_proposal_count": 2,
            }
        return {"completed_proposal_count": 2, "new_proposal_count": 0}

    monkeypatch.setattr(matched_smoke.empirical_support, "load_model", lambda path: {})
    monkeypatch.setattr(
        matched_smoke.matched_waymax, "WaymaxEvaluatorAdapter", Adapter
    )
    monkeypatch.setattr(matched_smoke.matched_coordinator, "run", coordinator_run)

    result = matched_smoke.run(
        manifest_path=Path("private-manifest.json"),
        support_model_path=Path("private-model.json"),
        output_dir=output,
    )

    assert calls[0]["cell"] == matched_smoke.SMOKE_CELL
    assert calls[0]["max_new_proposals"] == 2
    assert calls[1]["resume"] is True
    assert calls[1]["max_new_proposals"] == 0
    assert result["proposal_count"] == 2
    assert result["resume_repeated_evaluation_count"] == 0
    assert result["support_pass_count"] == 1
    assert result["original_physical_rollouts"] == 4
    assert result["proposal_physical_rollouts"] == 12
    assert result["total_physical_rollouts"] == 16
    serialized = json.dumps(result)
    assert "private-manifest" not in serialized
    assert "private-model" not in serialized
    assert "trajectory" not in serialized
