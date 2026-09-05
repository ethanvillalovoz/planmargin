"""Bounded local experiment supervision; no simulation imports in the API process.

Workers write progress and immutable results. Only this supervisor writes job
state. There is one worker per workspace, with a wall-time limit and no shell.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

MANIFEST = Path("artifacts/stage-0/scenario-selection.json")
SUPPORT = Path("artifacts/realism/lead-braking-support-v1-00c3727/model.json")
STANDARD_SUPPORT = Path("artifacts/realism/lead-braking-support-v1/model.json")
JOBS = Path("artifacts/local-experiments")
PROTOCOL = "interactive-lead-braking-v1"
MAX_SECONDS = 900
MAX_JOBS = 200
TERMINAL = frozenset(
    {"succeeded", "rejected", "failed", "cancelled", "interrupted", "timed_out"}
)
STAGES = {
    "starting": "Starting the local worker",
    "inputs": "Verifying licensed inputs",
    "loading": "Loading the selected WOMD scenario",
    "original_tested": "Running the original tested planner twice",
    "original_reference": "Running the original reference planner twice",
    "mutation": "Applying the bounded lead-vehicle change",
    "mutated_tested": "Running the changed tested planner twice",
    "mutated_reference": "Running the changed reference planner twice",
    "validation": "Evaluating realism and reproducibility",
    "export": "Verifying and retaining exact trajectories",
    "complete": "Experiment complete",
}
RECOVERY = {
    "inputs": "Prepare planning inputs with the planning setup command, then retry.",
    "loading": "Check Waymo access and source availability, then retry. No result was inferred.",
    "default": "Inspect this job's local worker.log, fix the reported component, then rerun as a new job.",
    "cancelled": "The worker was stopped. Rerun this configuration to start a new experiment.",
    "interrupted": "The server stopped before completion. Rerun this configuration; partial files are not results.",
    "timed_out": "The 15-minute local limit was reached. Inspect the last stage and local worker.log before retrying.",
}


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    selection_order: int = Field(ge=1, le=10)
    braking_onset_offset_s: float = Field(ge=0, le=0.5)
    speed_multiplier: float = Field(ge=0.75, le=1)

    @field_validator("braking_onset_offset_s")
    @classmethod
    def discrete_onset(cls, value: float) -> float:
        if value not in (0, 0.1, 0.2, 0.3, 0.4, 0.5):
            raise ValueError("Onset must use a 0.1-second increment")
        return value


class ExperimentRequest(ExperimentConfig):
    request_id: str = Field(pattern=r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path, limit: int = 1_048_576) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Expected a bounded regular experiment file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Experiment record must be an object")
    return value


def confined(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Invalid experiment path")
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("Experiment paths may not follow symlinks")
    return path


def support_path(root: Path) -> Path:
    """Prefer the reproduced standard artifact, preserving the legacy workspace."""
    standard = confined(root, STANDARD_SUPPORT)
    return standard if standard.is_file() else confined(root, SUPPORT)


class BusyError(RuntimeError):
    """The workspace is already running an experiment."""


class ExperimentJobs:
    def __init__(self, root: Path, *, max_seconds: float = MAX_SECONDS) -> None:
        self.root = root.resolve()
        self.directory = confined(self.root, JOBS)
        self.max_seconds = max_seconds
        self._lock = threading.RLock()
        self._process: subprocess.Popen[bytes] | None = None
        self._active: str | None = None
        self._started = 0.0
        self._lease: Any = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def open(self) -> None:
        self._stop.clear()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        lease = confined(self.root, JOBS / ".supervisor.lock")
        self._lease = lease.open("a")
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lease.close()
            raise BusyError(
                "Another experiment supervisor owns this workspace"
            ) from None
        try:
            for record in self.list():
                if record["status"] not in TERMINAL:
                    self._finish(record, "interrupted")
        except (ValueError, OSError):
            self._lease.close()
            raise
        self._thread = threading.Thread(
            target=self._watch, name="experiment-supervisor", daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        with self._lock:
            if self._active:
                self._terminate()
                self._finish(self.get(self._active), "interrupted")
                self._active = None
        if self._thread:
            self._thread.join(timeout=3)
        if self._lease:
            self._lease.close()

    def readiness(self) -> dict[str, Any]:
        missing = []
        for name, relative in (("scenario selection", MANIFEST),):
            if not confined(self.root, relative).is_file():
                missing.append(name)
        return {
            "ready": not missing,
            "missing": missing,
            "protocol": PROTOCOL,
            "empirical_support_ready": support_path(self.root).is_file(),
            "maximum_seconds": MAX_SECONDS,
            "maximum_concurrent_jobs": 1,
            "maximum_retained_jobs": MAX_JOBS,
            "setup_command": "uv run --frozen planmargin-prepare-planning --accept-waymo-terms",
            "boundary": "Local exploratory runs; never added to the frozen campaign. Two fixed Waymax IDM configurations.",
        }

    def path(self, job_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise KeyError(job_id)
        return confined(self.root, JOBS / job_id)

    def get(self, job_id: str) -> dict[str, Any]:
        path = self.path(job_id) / "state.json"
        if not path.exists():
            raise KeyError(job_id)
        record = read_json(path)
        if record.get("job_id") != job_id:
            raise ValueError("Experiment identity mismatch")
        return record

    def list(self) -> list[dict[str, Any]]:
        if not self.directory.exists():
            return []
        # A crash between mkdir and the first atomic state write can leave an
        # empty directory. It is not a job and must not disable the whole API.
        records = []
        for path in self.directory.iterdir():
            if re.fullmatch(r"[0-9a-f]{32}", path.name):
                self.path(path.name)  # Reject symlinks rather than following them.
                if (path / "state.json").exists():
                    records.append(self.get(path.name))
        return sorted(
            records,
            key=lambda item: item["created_at"],
            reverse=True,
        )

    def start(self, request: ExperimentRequest) -> dict[str, Any]:
        with self._lock:
            records = self.list()
            config = request.model_dump(exclude={"request_id"})
            for existing in records:
                if existing["request_id"] == request.request_id:
                    if existing["config"] != config:
                        raise ValueError(
                            "Request ID was already used for another configuration"
                        )
                    return existing
            if self._active:
                raise BusyError(
                    "One experiment is already running. Wait or cancel it first."
                )
            if len(records) >= MAX_JOBS:
                raise BusyError(
                    "Local history is full. Archive completed job folders outside the workspace before starting another."
                )
            if not self.readiness()["ready"]:
                raise ValueError(
                    "Planning inputs are missing. Run the planning setup command first."
                )
            job_id = uuid.uuid4().hex
            directory = self.path(job_id)
            directory.mkdir(mode=0o700)
            record = {
                "job_id": job_id,
                "request_id": request.request_id,
                "protocol": PROTOCOL,
                "config": config,
                "status": "running",
                "stage": "starting",
                "stage_label": STAGES["starting"],
                "created_at": time.time(),
                "finished_at": None,
                "elapsed_seconds": 0.0,
                "events": [],
                "error": None,
                "result": None,
            }
            write_json(directory / "state.json", record)
            write_json(
                directory / "request.json",
                {"job_id": job_id, "protocol": PROTOCOL, "config": config},
            )
            environment = dict(os.environ)
            for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                environment.pop(key, None)
            environment["PYTHONUNBUFFERED"] = "1"
            try:
                with (directory / "worker.log").open("xb") as log:
                    os.chmod(directory / "worker.log", 0o600)
                    self._process = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "planmargin.experiment_worker",
                            "--root",
                            str(self.root),
                            "--job-id",
                            job_id,
                        ],
                        cwd=self.root,
                        env=environment,
                        stdout=log,
                        stderr=log,
                        start_new_session=True,
                    )
                self._active = job_id
                self._started = time.monotonic()
            except OSError:
                self._finish(record, "failed", "worker_start_failed")
            return self.get(job_id)

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            record = self.get(job_id)
            if record["status"] in TERMINAL:
                return record
            if job_id != self._active:
                raise BusyError("This supervisor does not own that worker")
            self._terminate()
            self._finish(record, "cancelled")
            self._active = None
            return self.get(job_id)

    def result(self, job_id: str) -> dict[str, Any]:
        record = self.get(job_id)
        if record["status"] not in {"succeeded", "rejected"}:
            raise ValueError("This experiment has no verified result")
        return self._verified_result(job_id, record)

    def _verified_result(self, job_id: str, record: dict[str, Any]) -> dict[str, Any]:
        result = read_json(self.path(job_id) / "result.json")
        expected = result.get("result_sha256")
        if (
            expected
            != digest(
                {key: value for key, value in result.items() if key != "result_sha256"}
            )
            or result.get("job_id") != job_id
            or result.get("config") != record["config"]
            or result.get("protocol") != PROTOCOL
        ):
            raise ValueError("Experiment result integrity mismatch")
        return result

    def _terminate(self) -> None:
        if self._process and self._process.poll() is None:
            try:
                os.killpg(self._process.pid, signal.SIGTERM)
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(self._process.pid, signal.SIGKILL)
                self._process.wait(timeout=2)
            except ProcessLookupError:
                pass
        self._process = None

    def _finish(
        self, record: dict[str, Any], status: str, code: str | None = None
    ) -> None:
        record["status"] = status
        record["finished_at"] = time.time()
        record["elapsed_seconds"] = round(
            record["finished_at"] - record["created_at"], 3
        )
        if status in {"succeeded", "rejected"}:
            record["stage"] = "complete"
            record["stage_label"] = STAGES["complete"]
        else:
            record["error"] = {
                "code": code or status,
                "component": record["stage"],
                "recovery": RECOVERY.get(
                    status, RECOVERY.get(record["stage"], RECOVERY["default"])
                ),
            }
        for event in record["events"]:
            if event["status"] == "running":
                event["status"] = (
                    "completed" if status in {"succeeded", "rejected"} else "stopped"
                )
                event["duration_seconds"] = round(
                    max(0.0, record["elapsed_seconds"] - event["started_seconds"]), 3
                )
        write_json(self.path(record["job_id"]) / "state.json", record)

    def _watch(self) -> None:
        while not self._stop.wait(0.25):
            with self._lock:
                if not self._active or self._process is None:
                    continue
                record = self.get(self._active)
                try:
                    progress_path = self.path(self._active) / "progress.json"
                    if progress_path.exists():
                        progress = read_json(progress_path)
                        if progress.get("stage") not in STAGES:
                            raise ValueError("Invalid worker stage")
                        record.update(
                            stage=progress["stage"],
                            stage_label=STAGES[progress["stage"]],
                            events=progress.get("events", []),
                        )
                    record["elapsed_seconds"] = round(
                        time.monotonic() - self._started, 3
                    )
                    return_code = self._process.poll()
                    if (
                        return_code is None
                        and time.monotonic() - self._started > self.max_seconds
                    ):
                        self._terminate()
                        self._finish(record, "timed_out")
                        self._active = None
                    elif return_code is not None:
                        if return_code == 0:
                            result = self._verified_result(self._active, record)
                            record["result"] = result
                            self._finish(
                                record,
                                "rejected"
                                if result["decision"] == "invalid_mutation"
                                else "succeeded",
                            )
                        else:
                            self._finish(record, "failed", "worker_failed")
                        self._active = None
                        self._process = None
                    else:
                        write_json(self.path(self._active) / "state.json", record)
                except (ValueError, KeyError, OSError):
                    self._terminate()
                    self._finish(record, "failed", "result_integrity_failed")
                    self._active = None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-order", type=int, required=True)
    parser.add_argument("--onset", type=float, required=True)
    parser.add_argument("--speed", type=float, required=True)
    args = parser.parse_args()
    request = ExperimentRequest(
        selection_order=args.selection_order,
        braking_onset_offset_s=args.onset,
        speed_multiplier=args.speed,
        request_id=str(uuid.uuid4()),
    )
    jobs = ExperimentJobs(Path.cwd())
    jobs.open()
    try:
        record = jobs.start(request)
        while record["status"] not in TERMINAL:
            time.sleep(1)
            record = jobs.get(record["job_id"])
        print(json.dumps(record, indent=2))
        if record["status"] not in {"succeeded", "rejected"}:
            raise SystemExit(1)
    finally:
        jobs.close()
