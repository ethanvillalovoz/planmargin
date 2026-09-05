"""Authenticated local experiment routes, separate from frozen evidence reads."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from planmargin import rollout_record
from planmargin.experiment_health import summarize_health
from planmargin.experiment_jobs import (
    BusyError,
    ExperimentJobs,
    ExperimentRequest,
    read_json,
)


def experiment_router(
    jobs: ExperimentJobs,
    project_run: Callable[..., dict[str, Any]],
    authorize: Callable[..., None],
    authorize_write: Callable[..., None],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/experiments", dependencies=[Depends(authorize)])

    def lookup(job_id: str) -> dict[str, Any]:
        try:
            return jobs.get(job_id)
        except KeyError as error:
            raise HTTPException(
                status_code=404, detail="Experiment not found"
            ) from error

    @router.get("/readiness")
    def readiness() -> dict[str, Any]:
        return jobs.readiness()

    @router.get("")
    def history() -> list[dict[str, Any]]:
        return jobs.list()

    @router.get("/health")
    def live_health() -> dict[str, Any]:
        return summarize_health(jobs.list())

    @router.post("", status_code=202, dependencies=[Depends(authorize_write)])
    async def create(request: Request) -> dict[str, Any]:
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(
                status_code=415, detail="Expected JSON experiment configuration"
            )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                raise HTTPException(
                    status_code=413, detail="Experiment request is too large"
                )
        try:
            config = ExperimentRequest.model_validate_json(bytes(body))
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail="Invalid bounded test configuration. Choose a supported test plan, scenario 1–10 and deadline 10–900 s. Fault plans require unchanged traffic (onset 0, speed 1) and fixed controllers.",
            ) from error
        try:
            return jobs.start(config)
        except BusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail="Planning inputs are missing, the request ID was reused, or the linked rerun does not match a finished configuration.",
            ) from error

    @router.get("/{job_id}")
    def status(job_id: str) -> dict[str, Any]:
        return lookup(job_id)

    @router.post("/{job_id}/cancel", dependencies=[Depends(authorize_write)])
    def cancel(job_id: str) -> dict[str, Any]:
        lookup(job_id)
        try:
            return jobs.cancel(job_id)
        except BusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.get("/{job_id}/result")
    def result(job_id: str) -> dict[str, Any]:
        lookup(job_id)
        try:
            return jobs.result(job_id)
        except (ValueError, OSError) as error:
            raise HTTPException(
                status_code=409,
                detail="No verified result is available for this experiment",
            ) from error

    @router.get("/{job_id}/replay")
    def replay(job_id: str) -> dict[str, Any]:
        summary = result(job_id)
        try:
            path = jobs.path(job_id) / "collection.json"
            collection = read_json(path, limit=16 * 1024 * 1024)
            if (
                hashlib.sha256(path.read_bytes()).hexdigest()
                != summary["collection_sha256"]
            ):
                raise ValueError("Collection hash mismatch")
            if (
                rollout_record.validate_collection(collection)
                or collection["collection_status"] != "complete"
            ):
                raise ValueError("Collection validation failed")
            projected = project_run(
                collection,
                f"experiment_{job_id}",
                f"Local experiment · scenario {summary['config']['selection_order']}",
                "interactive-counterfactual",
                "New local experiment",
            )
            projected["hypothesis"]["supported"] = summary["gates"].get(
                "empirical_support", False
            )
            if summary["config"].get("test_plan", "lead_braking") != "lead_braking":
                projected["hypothesis"].update(
                    behavior_events=summary["behavior_events"],
                    behavior_decision=summary["decision"],
                    behavior_boundary=summary["boundary"],
                    trajectory_labels={
                        "tested": "Unprotected",
                        "reference": "Protected",
                        "recorded": "Primary baseline",
                    },
                    label=summary["config"]["test_plan"].replace("_", " ").capitalize(),
                    onset_seconds=2.0,
                )
            return projected
        except (ValueError, OSError, KeyError) as error:
            raise HTTPException(
                status_code=409, detail="This experiment has no verified replay"
            ) from error

    return router
