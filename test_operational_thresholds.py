from __future__ import annotations

from operational_thresholds import DEFAULT_THRESHOLDS, evaluate_thresholds, load_thresholds


def _healthy_snapshot() -> dict:
    return {
        "preflight_status": "PASS",
        "runtime": {
            "database": {"status": "PASS"},
            "checkpoint": {"status": "PRESENT", "age_seconds": 10},
            "backup": {"status": "PRESENT", "age_seconds": 20},
            "audit": {"status": "PRESENT", "age_seconds": 30},
            "anchor": {"status": "PRESENT", "age_seconds": 40},
            "disk": {"status": "PASS", "free_ratio": 0.50},
        },
    }


def run() -> None:
    thresholds = load_thresholds({})
    assert thresholds == DEFAULT_THRESHOLDS
    healthy = evaluate_thresholds(
        _healthy_snapshot(),
        metrics={"sync_backlog": 0, "worker_queue_backlog": 0, "unresolved_alerts": 0},
        thresholds=thresholds,
    )
    assert healthy["status"] == "PASS"
    assert healthy["resume_permitted"] is True
    assert healthy["checks"] == []

    missing = evaluate_thresholds(_healthy_snapshot(), metrics={})
    assert missing["status"] == "BLOCKED_REQUIRES_RECONCILIATION"
    assert missing["resume_permitted"] is False
    assert "SYNC_BACKLOG_NOT_COLLECTED" in missing["remediation_codes"]
    assert "WORKER_QUEUE_BACKLOG_NOT_COLLECTED" in missing["remediation_codes"]
    assert "UNRESOLVED_ALERTS_NOT_COLLECTED" in missing["remediation_codes"]

    unhealthy_snapshot = _healthy_snapshot()
    unhealthy_snapshot["preflight_status"] = "FAIL"
    unhealthy_snapshot["runtime"]["checkpoint"] = {"status": "PRESENT", "age_seconds": 301}
    unhealthy_snapshot["runtime"]["backup"] = {"status": "NOT_PRESENT_UNVERIFIED"}
    unhealthy_snapshot["runtime"]["disk"] = {"status": "ADVISORY", "free_ratio": 0.04}
    unhealthy = evaluate_thresholds(
        unhealthy_snapshot,
        metrics={"sync_backlog": 4, "worker_queue_backlog": "INVALID", "unresolved_alerts": 2},
    )
    assert unhealthy["status"] == "BLOCKED_REQUIRES_RECONCILIATION"
    assert unhealthy["resume_permitted"] is False
    for code in (
        "PREFLIGHT_NOT_PASS",
        "CHECKPOINT_STALE",
        "BACKUP_NOT_VERIFIED",
        "DISK_HEADROOM_LOW",
        "SYNC_BACKLOG_OVER_LIMIT",
        "WORKER_QUEUE_BACKLOG_INVALID",
        "UNRESOLVED_ALERTS_OVER_LIMIT",
    ):
        assert code in unhealthy["remediation_codes"]

    custom = load_thresholds(
        {
            "SW_MAX_CHECKPOINT_AGE_SECONDS": "600",
            "SW_MIN_DISK_FREE_RATIO": "0.20",
            "SW_MAX_SYNC_BACKLOG": "5",
        }
    )
    assert custom["max_checkpoint_age_seconds"] == 600
    assert custom["min_disk_free_ratio"] == 0.20
    assert custom["max_sync_backlog"] == 5

    for key, value in (
        ("SW_MAX_CHECKPOINT_AGE_SECONDS", "0"),
        ("SW_MIN_DISK_FREE_RATIO", "0.99"),
        ("SW_MAX_SYNC_BACKLOG", "-1"),
        ("SW_MAX_UNRESOLVED_ALERTS", "not-an-int"),
    ):
        try:
            load_thresholds({key: value})
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid threshold accepted: {key}={value}")
    print("[Thresholds] healthy pass, missing/stale/over-limit fail-closed: PASSED")
    print("[Thresholds] bounded policy parsing and remediation codes: PASSED")
    print("OPERATIONAL_THRESHOLDS_TESTS_PASSED")


if __name__ == "__main__":
    run()
