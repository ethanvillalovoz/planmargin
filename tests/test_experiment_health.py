"""Data-free diagnostic contracts; fixtures are never published as measurements."""

from planmargin.experiment_health import summarize_health


def job(identity, status="succeeded", **overrides):
    return {
        "job_id": identity,
        "created_at": ord(identity),
        "config": {"selection_order": 1},
        "status": status,
        "stage": "loading",
        "stage_label": "Loading scenario",
        "elapsed_seconds": 20,
        "completion_deadline_seconds": 120,
        "error": None,
        "result": {"decision": "not_qualified"},
        **overrides,
    }


def test_health_distinguishes_failure_lateness_behavior_and_cancel():
    jobs = [
        job("a", "failed"),
        job("b", elapsed_seconds=121),
        job("c", result={"decision": "checks_failed"}),
        job("d", "cancelled", elapsed_seconds=130),
        job("e"),
    ]
    health = summarize_health(jobs)
    assert health["status"] == "attention"
    assert [item["kind"] for item in health["incidents"]] == [
        "execution_failure",
        "completion_deadline_missed",
        "behavior_checks_failed",
    ]
    assert health["deadline_measured_jobs"] == 4
    assert (
        health["on_time_completed_jobs"] == 2
    )  # Execution success does not imply behavioral success.


def test_only_a_successful_linked_same_config_rerun_resolves():
    failed = job("a", "failed")
    assert summarize_health([failed, job("b")])["active_incidents"] == 1
    assert (
        summarize_health(
            [failed, job("b", rerun_of="a", config={"selection_order": 2})]
        )["active_incidents"]
        == 1
    )
    assert (
        summarize_health([failed, job("b", "cancelled", rerun_of="a")])[
            "active_incidents"
        ]
        == 1
    )
    assert (
        summarize_health([failed, job("b", rerun_of="a", elapsed_seconds=130)])[
            "active_incidents"
        ]
        == 2
    )
    health = summarize_health(
        [failed, job("b", "failed", rerun_of="a"), job("c", rerun_of="b")]
    )
    assert health["active_incidents"] == 0
    assert health["resolved_incidents"] == 2
    assert all(item["resolved_by"] == "c" for item in health["incidents"])
    assert failed["status"] == "failed"  # Historical record is never rewritten.


def test_old_records_remain_unmeasured_and_empty_workspace_is_not_healthy():
    old = job("a")
    del old["completion_deadline_seconds"]
    health = summarize_health([old])
    assert health["unmeasured_jobs"] == 1
    assert health["deadline_measured_jobs"] == 0
    assert summarize_health([])["status"] == "empty"


def test_running_job_misses_declared_deadline_before_hard_timeout():
    health = summarize_health([job("a", "running", elapsed_seconds=121)])
    assert health["active_incidents"] == 1
    assert health["deadline_measured_jobs"] == 0
    assert health["incidents"][0]["deadline_seconds"] == 120
