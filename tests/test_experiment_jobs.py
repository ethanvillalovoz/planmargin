"""Data-free lifecycle tests; fake workers here are test doubles, not evidence."""

from __future__ import annotations

import signal
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from planmargin import evidence_api, experiment_jobs as jobs_module
from planmargin.experiment_jobs import (
    BusyError,
    ExperimentJobs,
    ExperimentRequest,
    JOBS,
    MANIFEST,
    TERMINAL,
    confined,
    digest,
    read_json,
    write_json,
)
from planmargin.experiment_worker import Progress, build_tested_controller

TOKEN = "test-only-experiment-token-00000"
ORIGIN = "http://127.0.0.1:4200"


def request(**overrides):
    return ExperimentRequest.model_validate(
        {
            "request_id": str(uuid.uuid4()),
            "selection_order": 1,
            "braking_onset_offset_s": 0.0,
            "speed_multiplier": 0.9,
            **overrides,
        }
    )


class FakeProcess:
    pid = 987654321  # Never signalled: killpg is mocked below.
    returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        self.returncode = -signal.SIGTERM
        return self.returncode


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    manifest = tmp_path / MANIFEST
    manifest.parent.mkdir(parents=True)
    write_json(manifest, {"test_only": True})
    created = []

    def spawn(*args, **kwargs):
        process = FakeProcess()
        created.append((process, args, kwargs))
        return process

    monkeypatch.setattr(jobs_module.subprocess, "Popen", spawn)
    monkeypatch.setattr(jobs_module.os, "killpg", lambda *args: None)
    manager = ExperimentJobs(tmp_path)
    manager.open()
    yield manager, created
    manager.close()


def wait_finished(manager, job_id):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        record = manager.get(job_id)
        if record["status"] in TERMINAL:
            return record
        time.sleep(0.01)
    pytest.fail("Supervisor did not finish the test worker")


def seal_result(manager, record, decision="not_qualified"):
    value = {
        "job_id": record["job_id"],
        "protocol": record["protocol"],
        "config": record["config"],
        "execution": {
            key: record.get(key) for key in ("completion_deadline_seconds", "rerun_of")
        },
        "decision": decision,
        "collection_sha256": None,
    }
    value["result_sha256"] = digest(value)
    write_json(manager.path(record["job_id"]) / "result.json", value)
    return value


def test_fault_request_and_linked_rerun_preserve_identity(workspace):
    manager, created = workspace
    config = request(test_plan="assistance_handoff", speed_multiplier=1.0)
    first = manager.start(config)
    assert first["protocol"] == "interactive-assistance-handoff-v1"
    assert first["completion_deadline_seconds"] == 120
    manager.cancel(first["job_id"])
    with pytest.raises(ValueError, match="repeat a finished configuration"):
        manager.start(request(rerun_of=first["job_id"]))
    with pytest.raises(ValueError, match="does not exist"):
        manager.start(request(rerun_of="b" * 32))
    retry = request(
        test_plan="assistance_handoff",
        speed_multiplier=1.0,
        rerun_of=first["job_id"],
        completion_deadline_seconds=180,
    )
    second = manager.start(retry)
    assert second["rerun_of"] == first["job_id"]
    assert manager.start(retry)["job_id"] == second["job_id"]
    with pytest.raises(ValueError, match="already used"):
        manager.start(retry.model_copy(update={"completion_deadline_seconds": 240}))
    seal_result(manager, second, decision="checks_passed")
    created[-1][0].returncode = 0
    assert wait_finished(manager, second["job_id"])["status"] == "succeeded"
    assert manager.get(first["job_id"])["status"] == "cancelled"


def test_result_cannot_change_the_declared_execution_deadline(workspace):
    manager, created = workspace
    record = manager.start(request())
    result = seal_result(manager, record)
    result["execution"]["completion_deadline_seconds"] = 900
    result.pop("result_sha256")
    result["result_sha256"] = digest(result)
    write_json(manager.path(record["job_id"]) / "result.json", result)
    created[-1][0].returncode = 0
    assert wait_finished(manager, record["job_id"])["status"] == "failed"


@pytest.mark.parametrize(
    "overrides",
    [
        {"selection_order": 0},
        {"selection_order": 11},
        {"selection_order": True},
        {"speed_multiplier": 0.749},
        {"speed_multiplier": 1.01},
        {"speed_multiplier": float("nan")},
        {"speed_multiplier": "0.9"},
        {"braking_onset_offset_s": 0.15},
        {"braking_onset_offset_s": -0.1},
        {"braking_onset_offset_s": 0.6},
        {"command": "arbitrary"},
        {"tested_controller": {"command": "arbitrary"}},
        {"tested_controller": {"desired_vel_mps": 41}},
        {"tested_controller": {"desired_vel_mps": "20"}},
        {"tested_controller": {"min_spacing_m": 0}},
        {"tested_controller": {"safe_time_headway_s": float("nan")}},
        {"tested_controller": {"safe_time_headway_s": float("inf")}},
        {"tested_controller": {"safe_time_headway_s": True}},
        {"tested_controller": {"safe_time_headway_s": 5.1}},
        {"request_id": "../../outside"},
        {"test_plan": "shell"},
        {"test_plan": "command_dropout"},
        {
            "test_plan": "assistance_handoff",
            "speed_multiplier": 1.0,
            "tested_controller": {},
        },
        {"completion_deadline_seconds": 9},
        {"completion_deadline_seconds": 901},
        {"completion_deadline_seconds": True},
        {"rerun_of": "../../outside"},
    ],
)
def test_configuration_is_bounded(overrides):
    with pytest.raises(ValidationError):
        request(**overrides)


def test_custom_controller_is_content_addressed_and_preserves_frozen_defaults():
    from planmargin.controller_comparison import TESTED_CONTROLLER, REFERENCE_CONTROLLER

    frozen_tested, frozen_reference = (
        TESTED_CONTROLLER.report(),
        REFERENCE_CONTROLLER.report(),
    )
    assert build_tested_controller(request()) is TESTED_CONTROLLER
    assert "tested_controller" not in request().record()
    config = request(
        tested_controller={"desired_vel_mps": 24.0, "safe_time_headway_s": 2.5}
    )
    spec = build_tested_controller(config)
    assert spec.desired_vel_mps == 24
    assert spec.safe_time_headway_s == 2.5
    assert spec.min_spacing_m == 2
    assert spec.role == "tested"
    assert spec.controller_id.startswith("planmargin-custom-idm-")
    assert spec == build_tested_controller(config)
    assert (
        spec.controller_id
        != build_tested_controller(
            request(tested_controller={"desired_vel_mps": 25.0})
        ).controller_id
    )
    assert TESTED_CONTROLLER.report() == frozen_tested
    assert REFERENCE_CONTROLLER.report() == frozen_reference
    assert config.record()["tested_controller"] == {
        "desired_vel_mps": 24.0,
        "min_spacing_m": 2.0,
        "safe_time_headway_s": 2.5,
    }
    # Verify the actual Waymax policy receives the custom values.
    policy = spec.build()
    default_policy = TESTED_CONTROLLER.build()
    assert type(policy) is type(default_policy)


def test_custom_settings_are_sealed_and_part_of_submission_identity(workspace):
    manager, _ = workspace
    req = request(tested_controller={"min_spacing_m": 3.0})
    record = manager.start(req)
    assert (
        read_json(manager.path(record["job_id"]) / "request.json")["config"]
        == req.record()
    )
    assert record["config"]["tested_controller"]["min_spacing_m"] == 3
    with pytest.raises(ValueError, match="another configuration"):
        manager.start(
            request(request_id=req.request_id, tested_controller={"min_spacing_m": 4.0})
        )


def test_idempotency_one_worker_and_secret_scope(workspace, monkeypatch):
    manager, processes = workspace
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-secret")
    req = request()
    record = manager.start(req)
    assert manager.start(req)["job_id"] == record["job_id"]
    assert len(processes) == 1
    with pytest.raises(BusyError):
        manager.start(request())
    with pytest.raises(ValueError):
        manager.start(request(request_id=req.request_id, speed_multiplier=0.8))
    _, args, kwargs = processes[0]
    assert "shell" not in kwargs
    assert kwargs["start_new_session"] is True
    assert "GEMINI_API_KEY" not in kwargs["env"]
    assert args[0][1:3] == ["-m", "planmargin.experiment_worker"]
    assert (
        manager.path(record["job_id"]) / "worker.log"
    ).stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "decision,status",
    [("not_qualified", "succeeded"), ("invalid_mutation", "rejected")],
)
def test_completed_worker_requires_verified_result(workspace, decision, status):
    manager, processes = workspace
    record = manager.start(request())
    seal_result(manager, record, decision)
    processes[-1][0].returncode = 0
    completed = wait_finished(manager, record["job_id"])
    assert completed["status"] == status
    assert completed["error"] is None
    assert manager.result(record["job_id"])["decision"] == decision


@pytest.mark.parametrize(
    "exitcode,code", [(0, "result_integrity_failed"), (2, "worker_failed")]
)
def test_bad_worker_never_becomes_a_success(workspace, exitcode, code):
    manager, processes = workspace
    record = manager.start(request())
    processes[-1][0].returncode = exitcode
    failed = wait_finished(manager, record["job_id"])
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == code
    assert failed["result"] is None
    with pytest.raises(ValueError):
        manager.result(record["job_id"])


def test_tampered_result_is_not_exported(workspace):
    manager, processes = workspace
    record = manager.start(request())
    value = seal_result(manager, record)
    processes[-1][0].returncode = 0
    wait_finished(manager, record["job_id"])
    value["decision"] = "qualified"
    write_json(manager.path(record["job_id"]) / "result.json", value)
    with pytest.raises(ValueError, match="integrity"):
        manager.result(record["job_id"])


def test_cancel_is_persistent_and_idempotent(workspace):
    manager, _ = workspace
    record = manager.start(request())
    assert manager.cancel(record["job_id"])["status"] == "cancelled"
    assert manager.cancel(record["job_id"])["status"] == "cancelled"
    assert manager.start(request())["job_id"] != record["job_id"]


def test_timeout_stops_owned_worker(workspace):
    manager, _ = workspace
    manager.max_seconds = 0.01
    record = manager.start(request())
    assert wait_finished(manager, record["job_id"])["status"] == "timed_out"


def test_restart_preserves_history_marks_incomplete_and_ignores_empty_directory(
    workspace,
):
    manager, _ = workspace
    record = manager.start(request())
    manager.close()
    # Model an abrupt interruption before the manager wrote its final state.
    write_json(manager.path(record["job_id"]) / "state.json", record)
    manager.path(uuid.uuid4().hex).mkdir()
    reopened = ExperimentJobs(manager.root)
    reopened.open()
    try:
        assert len(reopened.list()) == 1
        assert reopened.get(record["job_id"])["status"] == "interrupted"
    finally:
        reopened.close()


def test_only_one_supervisor_can_own_workspace(workspace):
    manager, _ = workspace
    second = ExperimentJobs(manager.root)
    with pytest.raises(BusyError):
        second.open()


def test_confined_paths_reject_symlinks(tmp_path):
    (tmp_path / "artifacts").symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        confined(tmp_path, JOBS)
    with pytest.raises(ValueError):
        confined(tmp_path, Path("../outside"))


def test_final_progress_is_completed(tmp_path):
    progress = Progress(tmp_path)
    progress.stage("inputs")
    progress.stage("complete")
    assert all(
        item["status"] == "completed"
        for item in read_json(tmp_path / "progress.json")["events"]
    )


def test_planning_only_api_auth_csrf_and_missing_setup(tmp_path):
    app = evidence_api.create_app(root=tmp_path, token=TOKEN, planning_only=True)
    headers = {"X-PlanMargin-Token": TOKEN}
    with TestClient(app) as client:
        assert client.get("/api/v1/experiments").status_code == 401
        assert client.get("/api/v1/experiments/health").status_code == 401
        assert (
            client.get("/api/v1/experiments/health", headers=headers).json()["status"]
            == "empty"
        )
        assert (
            client.get("/api/v1/health", headers=headers).json()["campaign_ready"]
            is False
        )
        assert client.get("/api/v1/campaign", headers=headers).status_code == 503
        assert (
            client.get("/api/v1/experiments/readiness", headers=headers).json()["ready"]
            is False
        )
        body = request().model_dump()
        assert (
            client.post("/api/v1/experiments", headers=headers, json=body).status_code
            == 422
        )
        assert client.post("/api/v1/session", headers=headers).status_code == 204
        assert client.post("/api/v1/experiments", json=body).status_code == 403
        assert (
            client.post(
                "/api/v1/experiments",
                json=body,
                headers={"Origin": "https://untrusted.example"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/experiments",
                json=body,
                headers={**headers, "Origin": "https://untrusted.example"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/experiments",
                content="{}",
                headers={"Origin": ORIGIN, "Content-Type": "text/plain"},
            ).status_code
            == 415
        )
        assert (
            client.post(
                "/api/v1/experiments",
                content='"' + "x" * 4096 + '"',
                headers={"Origin": ORIGIN, "Content-Type": "application/json"},
            ).status_code
            == 413
        )
        assert (
            client.get("/api/v1/experiments/" + "a" * 32, headers=headers).status_code
            == 404
        )


def test_api_create_poll_cancel_and_idempotency(workspace):
    manager, _ = workspace
    manager.close()
    app = evidence_api.create_app(root=manager.root, token=TOKEN, planning_only=True)
    headers = {"X-PlanMargin-Token": TOKEN, "Origin": ORIGIN}
    with TestClient(app) as client:
        body = request().model_dump()
        response = client.post("/api/v1/experiments", json=body, headers=headers)
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        assert (
            client.post("/api/v1/experiments", json=body, headers=headers).json()[
                "job_id"
            ]
            == job_id
        )
        assert (
            client.post(
                "/api/v1/experiments", json=request().model_dump(), headers=headers
            ).status_code
            == 409
        )
        assert (
            client.get(
                f"/api/v1/experiments/{job_id}/result", headers=headers
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/v1/experiments/{job_id}/cancel", json={}, headers=headers
            ).json()["status"]
            == "cancelled"
        )
        assert (
            client.get("/api/v1/experiments", headers=headers).json()[0]["status"]
            == "cancelled"
        )
