"""Live, local execution diagnostics. Never rewrites frozen research evidence."""

from __future__ import annotations

from typing import Any

FAILURES = {"failed", "interrupted", "timed_out"}


def summarize_health(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve incidents only through an explicit, successful same-config rerun.

    Missing historical deadlines stay unmeasured. Cancellation and a negative
    lead-braking finding are not infrastructure failures. No fleet SLO is inferred.
    """
    by_id = {job["job_id"]: job for job in jobs}

    def issues(job: dict[str, Any]) -> list[str]:
        kinds = []
        if job["status"] in FAILURES:
            kinds.append("execution_failure")
        deadline = job.get("completion_deadline_seconds")
        if (
            deadline is not None
            and job["status"] != "cancelled"
            and job["elapsed_seconds"] > deadline
        ):
            kinds.append("completion_deadline_missed")
        if (job.get("result") or {}).get("decision") == "checks_failed":
            kinds.append("behavior_checks_failed")
        return kinds

    resolved_by: dict[str, str] = {}
    for job in sorted(jobs, key=lambda item: item["created_at"]):
        if job["status"] != "succeeded" or issues(job):
            continue
        parent_id = job.get("rerun_of")
        visited = {job["job_id"]}
        while parent_id in by_id and parent_id not in visited:
            visited.add(parent_id)
            parent = by_id[parent_id]
            if (
                parent["config"] != job["config"]
                or parent["created_at"] >= job["created_at"]
            ):
                break
            resolved_by.setdefault(parent_id, job["job_id"])
            parent_id = parent.get("rerun_of")

    incidents = []
    for job in jobs:
        for kind in issues(job):
            error = job.get("error") or {}
            incidents.append(
                {
                    "job_id": job["job_id"],
                    "kind": kind,
                    "test_plan": job["config"].get("test_plan", "lead_braking"),
                    "selection_order": job["config"]["selection_order"],
                    "component": error.get("component", job["stage"]),
                    "stage_label": job["stage_label"],
                    "elapsed_seconds": job["elapsed_seconds"],
                    "deadline_seconds": job.get("completion_deadline_seconds"),
                    "recovery": error.get("recovery")
                    or (
                        "Inspect the failed behavior gates and replay; rerun to verify the same protocol."
                        if kind == "behavior_checks_failed"
                        else "Inspect stage timings. Rerun with a realistic, declared deadline; the original miss remains recorded."
                    ),
                    "resolved_by": resolved_by.get(job["job_id"]),
                }
            )
    measured = [
        job
        for job in jobs
        if job.get("completion_deadline_seconds") is not None
        and job["status"] not in {"running", "cancelled"}
    ]
    active = sum(item["resolved_by"] is None for item in incidents)
    return {
        "schema_version": "1.0.0",
        "source": "local_experiment_history",
        "status": "attention"
        if active
        else "running"
        if any(job["status"] == "running" for job in jobs)
        else "healthy"
        if jobs
        else "empty",
        "total_jobs": len(jobs),
        "active_incidents": active,
        "resolved_incidents": len(incidents) - active,
        "deadline_measured_jobs": len(measured),
        "on_time_completed_jobs": sum(
            job["status"] in {"succeeded", "rejected"}
            and job["elapsed_seconds"] <= job["completion_deadline_seconds"]
            for job in measured
        ),
        "unmeasured_jobs": sum(
            job.get("completion_deadline_seconds") is None for job in jobs
        ),
        "incidents": incidents,
        "boundary": "This workspace only. All retained jobs; no rolling-window or fleet-health claim. Resolutions preserve original failures.",
    }
