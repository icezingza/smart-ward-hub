from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from deployment_readiness import validate_environment
from external_decision_lifecycle import AUTHORIZATION_BOUNDARY


SCHEMA_VERSION = "smart-ward-hub-internal-foundation-v1"
RUNTIME_ARTIFACT_NAMES = {
    "ward_hub.db",
    "ward_hub.db-shm",
    "ward_hub.db-wal",
    "audit_events.jsonl",
    "edge_telemetry_state.json",
    "forensic_anchors.jsonl",
    "reliability_validation_result.json",
    "pilot_simulation_result.json",
    "telemetry.jsonl",
    "serial_bench_evidence.json",
}
PRIVATE_KEY_MARKERS = tuple(
    "-----BEGIN " + label + "-----"
    for label in (
        "PRIVATE" + " " + "KEY",
        "RSA" + " " + "PRIVATE" + " " + "KEY",
        "EC" + " " + "PRIVATE" + " " + "KEY",
        "OPENSSH" + " " + "PRIVATE" + " " + "KEY",
    )
)
TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".env", ".example", ".ini", ".sh"}
NUMERIC_BOUNDS = {
    "SW_TELEMETRY_CHECKPOINT_EVERY": (1, 100_000, "positive checkpoint interval"),
    "SW_TELEMETRY_BUFFER_MAX_SAMPLES": (1, 500_000, "bounded telemetry buffer"),
    "SW_TELEMETRY_MAX_DEVICES": (1, 10_000, "bounded telemetry device count"),
    "SW_TELEMETRY_MAX_SAMPLE_BYTES": (256, 1_048_576, "bounded telemetry sample size"),
    "SW_SQLITE_BUSY_TIMEOUT_MS": (100, 120_000, "bounded SQLite busy timeout"),
    "SW_RATE_LIMIT_PER_MINUTE": (1, 1_000_000, "bounded request rate limit"),
    "SW_IDEMPOTENCY_TTL_SECONDS": (60, 604_800, "bounded idempotency retention"),
    "SW_DEVICE_TRUST_CLOCK_SKEW_SECONDS": (0, 3_600, "bounded device clock skew"),
}
MEMORY_ALARM_RATIO_ENV = "SW_TELEMETRY_MEMORY_ALARM_RATIO"


class InternalFoundationError(ValueError):
    pass


def _check(checks: list[dict[str, str]], name: str, status: str, detail: str) -> None:
    checks.append({"check": name, "status": status, "detail": detail})


def _numeric_bounds(env: Mapping[str, str], checks: list[dict[str, str]]) -> None:
    for name, (lower, upper, description) in NUMERIC_BOUNDS.items():
        raw = env.get(name)
        if raw is None or not raw.strip():
            _check(checks, name, "PASS", f"default is used; {description} remains bounded by code contract")
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            _check(checks, name, "FAIL", "must be an integer")
            continue
        if lower <= value <= upper:
            _check(checks, name, "PASS", f"{value} within [{lower}, {upper}]")
        else:
            _check(checks, name, "FAIL", f"{value} outside [{lower}, {upper}]")

    raw_ratio = env.get(MEMORY_ALARM_RATIO_ENV)
    if raw_ratio is None or not raw_ratio.strip():
        _check(checks, MEMORY_ALARM_RATIO_ENV, "PASS", "default is used; memory alarm ratio remains bounded by code contract")
    else:
        try:
            ratio = float(raw_ratio)
        except (TypeError, ValueError):
            _check(checks, MEMORY_ALARM_RATIO_ENV, "FAIL", "must be a number")
        else:
            if 0.5 <= ratio <= 1.0:
                _check(checks, MEMORY_ALARM_RATIO_ENV, "PASS", f"{ratio} within [0.5, 1.0]")
            else:
                _check(checks, MEMORY_ALARM_RATIO_ENV, "FAIL", f"{ratio} outside [0.5, 1.0]")


def _runtime_artifact_check(project_root: Path, checks: list[dict[str, str]]) -> None:
    found = sorted(
        str(path.relative_to(project_root))
        for path in project_root.rglob("*")
        if path.is_file() and path.name in RUNTIME_ARTIFACT_NAMES and ".git" not in path.parts
    )
    if found:
        _check(checks, "runtime_artifact_hygiene", "FAIL", "runtime artifacts must not remain in the source tree: " + ", ".join(found))
    else:
        _check(checks, "runtime_artifact_hygiene", "PASS", "known runtime artifacts absent from source tree")


def _private_material_check(project_root: Path, checks: list[dict[str, str]]) -> None:
    hits: list[str] = []
    for path in project_root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(marker in text for marker in PRIVATE_KEY_MARKERS):
            hits.append(str(path.relative_to(project_root)))
    if hits:
        _check(checks, "private_material_scan", "FAIL", "private-key marker found: " + ", ".join(sorted(hits)))
    else:
        _check(checks, "private_material_scan", "PASS", "no private-key marker found in repository text artifacts")


def _authorization_check(checks: list[dict[str, str]]) -> None:
    if AUTHORIZATION_BOUNDARY == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }:
        _check(checks, "authorization_boundary", "PASS", "locked NONE/false boundary is unchanged")
    else:
        _check(checks, "authorization_boundary", "FAIL", "authorization boundary differs from locked baseline")


def evaluate_internal_foundation(
    env: Mapping[str, str],
    *,
    project_root: Path,
    bind_host: str = "127.0.0.1",
    port: int = 8080,
) -> dict[str, object]:
    root = project_root.resolve()
    if not root.is_dir():
        raise InternalFoundationError("project_root must be an existing directory")

    checks: list[dict[str, str]] = []
    deployment = validate_environment(env, project_root=root, bind_host=bind_host, port=port)
    checks.extend(deployment.checks)
    _numeric_bounds(env, checks)
    _runtime_artifact_check(root, checks)
    _private_material_check(root, checks)
    _authorization_check(checks)

    statuses = {item["status"] for item in checks}
    status = "FAIL" if "FAIL" in statuses else "ADVISORY" if "ADVISORY" in statuses else "PASS"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "checks": checks,
        "software_only": True,
        "physical_validation": "UNVERIFIED",
        "clinical_validation": "PENDING",
        "external_authority": AUTHORIZATION_BOUNDARY["external_authority"],
        "runtime_authority": AUTHORIZATION_BOUNDARY["runtime_authority"],
        "authorization_boundary": dict(AUTHORIZATION_BOUNDARY),
        "pilot_gate_status": AUTHORIZATION_BOUNDARY["pilot_gate_status"],
    }


def main() -> int:
    result = evaluate_internal_foundation(dict(os.environ), project_root=Path(__file__).resolve().parent)
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if result["status"] != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
