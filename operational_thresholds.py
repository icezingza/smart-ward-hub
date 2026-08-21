from __future__ import annotations

from typing import Any, Mapping


SCHEMA_VERSION = "smart-ward-operational-thresholds-v1"

DEFAULT_THRESHOLDS: dict[str, int | float] = {
    "max_checkpoint_age_seconds": 300,
    "max_backup_age_seconds": 86_400,
    "max_audit_age_seconds": 86_400,
    "max_anchor_age_seconds": 86_400,
    "min_disk_free_ratio": 0.10,
    "max_sync_backlog": 0,
    "max_worker_queue_backlog": 0,
    "max_unresolved_alerts": 0,
}

THRESHOLD_ENV_KEYS = {
    "max_checkpoint_age_seconds": "SW_MAX_CHECKPOINT_AGE_SECONDS",
    "max_backup_age_seconds": "SW_MAX_BACKUP_AGE_SECONDS",
    "max_audit_age_seconds": "SW_MAX_AUDIT_AGE_SECONDS",
    "max_anchor_age_seconds": "SW_MAX_ANCHOR_AGE_SECONDS",
    "min_disk_free_ratio": "SW_MIN_DISK_FREE_RATIO",
    "max_sync_backlog": "SW_MAX_SYNC_BACKLOG",
    "max_worker_queue_backlog": "SW_MAX_WORKER_QUEUE_BACKLOG",
    "max_unresolved_alerts": "SW_MAX_UNRESOLVED_ALERTS",
}


def _bounded_int(value: str, *, field: str, lower: int, upper: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if not lower <= parsed <= upper:
        raise ValueError(f"{field} out of bounded range")
    return parsed


def _bounded_float(value: str, *, field: str, lower: float, upper: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not lower <= parsed <= upper:
        raise ValueError(f"{field} out of bounded range")
    return parsed


def load_thresholds(env: Mapping[str, str]) -> dict[str, int | float]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    for field, env_key in THRESHOLD_ENV_KEYS.items():
        raw = env.get(env_key)
        if raw is None or raw == "":
            continue
        if field == "min_disk_free_ratio":
            thresholds[field] = _bounded_float(raw, field=field, lower=0.05, upper=0.50)
        elif field.endswith("age_seconds"):
            thresholds[field] = _bounded_int(raw, field=field, lower=1, upper=30 * 86_400)
        else:
            thresholds[field] = _bounded_int(raw, field=field, lower=0, upper=1_000_000)
    return thresholds


def collect_optional_metrics(env: Mapping[str, str]) -> dict[str, int | str | None]:
    metric_keys = {
        "sync_backlog": "SW_SYNC_BACKLOG",
        "worker_queue_backlog": "SW_WORKER_QUEUE_BACKLOG",
        "unresolved_alerts": "SW_UNRESOLVED_ALERTS",
    }
    metrics: dict[str, int | str | None] = {}
    for metric, env_key in metric_keys.items():
        raw = env.get(env_key)
        if raw is None or raw == "":
            metrics[metric] = None
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            metrics[metric] = "INVALID"
            continue
        metrics[metric] = value if value >= 0 else "INVALID"
    return metrics


def _check(code: str, status: str, *, severity: str = "BLOCK", observed: Any = None, limit: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "status": status, "severity": severity}
    if observed is not None:
        result["observed"] = observed
    if limit is not None:
        result["limit"] = limit
    return result


def evaluate_thresholds(
    snapshot: Mapping[str, Any],
    *,
    metrics: Mapping[str, int | str | None] | None = None,
    thresholds: Mapping[str, int | float] | None = None,
) -> dict[str, Any]:
    policy = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
    runtime = snapshot.get("runtime") if isinstance(snapshot.get("runtime"), Mapping) else {}
    checks: list[dict[str, Any]] = []

    if snapshot.get("preflight_status") != "PASS":
        checks.append(_check("PREFLIGHT_NOT_PASS", "FAIL", observed=snapshot.get("preflight_status")))

    database = runtime.get("database", {}) if isinstance(runtime.get("database"), Mapping) else {}
    if database.get("status") != "PASS":
        checks.append(_check("DATABASE_NOT_VERIFIED", "FAIL", observed=database.get("status")))

    freshness_rules = (
        ("checkpoint", "max_checkpoint_age_seconds", "CHECKPOINT_NOT_VERIFIED", "CHECKPOINT_STALE"),
        ("backup", "max_backup_age_seconds", "BACKUP_NOT_VERIFIED", "BACKUP_STALE"),
        ("audit", "max_audit_age_seconds", "AUDIT_NOT_VERIFIED", "AUDIT_STALE"),
        ("anchor", "max_anchor_age_seconds", "ANCHOR_NOT_VERIFIED", "ANCHOR_STALE"),
    )
    for component, limit_key, missing_code, stale_code in freshness_rules:
        state = runtime.get(component, {}) if isinstance(runtime.get(component), Mapping) else {}
        if state.get("status") != "PRESENT":
            checks.append(_check(missing_code, "FAIL", observed=state.get("status"), limit=policy[limit_key]))
            continue
        age = state.get("age_seconds")
        if not isinstance(age, (int, float)) or isinstance(age, bool):
            checks.append(_check(missing_code, "FAIL", observed="AGE_UNAVAILABLE", limit=policy[limit_key]))
        elif age > policy[limit_key]:
            checks.append(_check(stale_code, "FAIL", observed=age, limit=policy[limit_key]))

    disk = runtime.get("disk", {}) if isinstance(runtime.get("disk"), Mapping) else {}
    free_ratio = disk.get("free_ratio")
    if not isinstance(free_ratio, (int, float)) or isinstance(free_ratio, bool):
        checks.append(_check("DISK_HEADROOM_UNVERIFIED", "FAIL", observed=disk.get("status"), limit=policy["min_disk_free_ratio"]))
    elif free_ratio < policy["min_disk_free_ratio"]:
        checks.append(_check("DISK_HEADROOM_LOW", "FAIL", observed=free_ratio, limit=policy["min_disk_free_ratio"]))

    observed_metrics = dict(metrics or {})
    for metric, limit_key, code in (
        ("sync_backlog", "max_sync_backlog", "SYNC_BACKLOG_OVER_LIMIT"),
        ("worker_queue_backlog", "max_worker_queue_backlog", "WORKER_QUEUE_BACKLOG_OVER_LIMIT"),
        ("unresolved_alerts", "max_unresolved_alerts", "UNRESOLVED_ALERTS_OVER_LIMIT"),
    ):
        value = observed_metrics.get(metric)
        if value is None:
            checks.append(_check(f"{metric.upper()}_NOT_COLLECTED", "FAIL", observed="NOT_COLLECTED", limit=policy[limit_key]))
        elif value == "INVALID":
            checks.append(_check(f"{metric.upper()}_INVALID", "FAIL", observed=value, limit=policy[limit_key]))
        elif value > policy[limit_key]:
            checks.append(_check(code, "FAIL", observed=value, limit=policy[limit_key]))

    remediation_codes = sorted({item["code"] for item in checks if item["status"] == "FAIL"})
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_class": "OPERATOR_DEFAULT_NOT_CLINICAL_THRESHOLD",
        "thresholds": policy,
        "checks": checks,
        "status": "PASS" if not remediation_codes else "BLOCKED_REQUIRES_RECONCILIATION",
        "resume_permitted": not remediation_codes,
        "remediation_codes": remediation_codes,
    }
