from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any


class BenchEvidenceValidationError(ValueError):
    pass


TEST_IDS = tuple(f"S-{index:03d}" for index in range(1, 16))
ALLOWED_TEST_STATUSES = {"PASS", "FAIL", "NOT_RUN", "BLOCKED", "UNVERIFIED"}
FORBIDDEN_VALUE_MARKERS = re.compile(
    r"(?i)(patient[_ -]?id|patient[_ -]?token|patient[_ -]?name|hospital[_ -]?number|\bhn\b|\bmrn\b|national[_ -]?id|bearer\s+|private[_ -]?key|secret|password|api[_ -]?key)"
)


def _canonical_payload(evidence: dict[str, Any]) -> bytes:
    payload = deepcopy(evidence)
    payload.pop("evidence_payload_sha256", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def evidence_payload_sha256(evidence: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_payload(evidence)).hexdigest()


def _scan_values(value: Any, path: str = "root") -> None:
    if isinstance(value, str):
        if FORBIDDEN_VALUE_MARKERS.search(value):
            raise BenchEvidenceValidationError(f"forbidden marker in evidence value at {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _scan_values(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise BenchEvidenceValidationError(f"non-string evidence key at {path}")
            _scan_values(item, f"{path}.{key}")
        return
    if value is not None and not isinstance(value, (bool, int, float)):
        raise BenchEvidenceValidationError(f"unsupported evidence value at {path}")


def _require(evidence: dict[str, Any], key: str) -> Any:
    if key not in evidence:
        raise BenchEvidenceValidationError(f"missing evidence field: {key}")
    return evidence[key]


def validate_bench_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise BenchEvidenceValidationError("evidence must be an object")
    _scan_values(evidence)

    required = (
        "run_id",
        "mode",
        "status",
        "tests",
        "test_scope",
        "physical_hardware_validation",
        "production_network_validation",
        "patient_data_used",
        "private_key_used",
        "raw_frames_recorded",
        "physical_confirmation_verified",
        "evidence_payload_sha256",
    )
    for key in required:
        _require(evidence, key)

    if not isinstance(evidence["run_id"], str) or not re.fullmatch(r"serial-bench-[A-Za-z0-9T:_-]{8,80}", evidence["run_id"]):
        raise BenchEvidenceValidationError("run_id is not bounded")
    if evidence["mode"] not in {"dry_run", "physical_loopback"}:
        raise BenchEvidenceValidationError("unsupported bench mode")
    if evidence["status"] not in {"DRY_RUN_ONLY", "NOT_STARTED", "BLOCKED_NO_PORT", "BLOCKED_CONFIRMATION_REQUIRED", "BLOCKED_DEPENDENCY", "PHYSICAL_IO_ERROR", "FAILED", "PASSED"}:
        raise BenchEvidenceValidationError("unsupported bench status")
    if not isinstance(evidence["tests"], dict) or set(evidence["tests"]) != set(TEST_IDS):
        raise BenchEvidenceValidationError("tests must cover exactly S-001 through S-015")
    if any(status not in ALLOWED_TEST_STATUSES for status in evidence["tests"].values()):
        raise BenchEvidenceValidationError("unsupported test status")
    if not isinstance(evidence["test_scope"], list) or any(test_id not in TEST_IDS for test_id in evidence["test_scope"]):
        raise BenchEvidenceValidationError("test_scope contains unknown test")
    if evidence["patient_data_used"] is not False or evidence["private_key_used"] is not False or evidence["raw_frames_recorded"] is not False:
        raise BenchEvidenceValidationError("redaction boundary is not fail-closed")
    if evidence["production_network_validation"] != "PENDING":
        raise BenchEvidenceValidationError("production network validation cannot be asserted by bench runner")
    if not isinstance(evidence["physical_confirmation_verified"], bool):
        raise BenchEvidenceValidationError("physical confirmation flag must be boolean")
    if evidence["mode"] == "dry_run":
        if evidence["status"] != "DRY_RUN_ONLY" or evidence["physical_confirmation_verified"]:
            raise BenchEvidenceValidationError("dry-run state is inconsistent")
        if evidence["physical_hardware_validation"] != "PENDING":
            raise BenchEvidenceValidationError("dry-run cannot verify physical hardware")
    if evidence["status"] == "PASSED":
        if evidence["mode"] != "physical_loopback" or not evidence["physical_confirmation_verified"]:
            raise BenchEvidenceValidationError("passed physical evidence lacks explicit confirmation")
        if evidence["physical_hardware_validation"] != "VERIFIED":
            raise BenchEvidenceValidationError("passed physical evidence lacks hardware verification state")
        if evidence["tests"].get("S-003") != "PASS" or "S-003" not in evidence["test_scope"]:
            raise BenchEvidenceValidationError("passed loopback evidence must bind S-003")
    if evidence["mode"] == "physical_loopback" and evidence["status"] in {"NOT_STARTED", "BLOCKED_NO_PORT", "BLOCKED_CONFIRMATION_REQUIRED", "BLOCKED_DEPENDENCY", "PHYSICAL_IO_ERROR", "FAILED"} and evidence["physical_hardware_validation"] == "VERIFIED":
        raise BenchEvidenceValidationError("failed/blocked physical run cannot claim verified hardware")

    expected_hash = evidence_payload_sha256(evidence)
    if evidence["evidence_payload_sha256"] != expected_hash:
        raise BenchEvidenceValidationError("evidence payload hash mismatch")
    return {"valid": True, "test_ids": list(TEST_IDS), "status": evidence["status"], "mode": evidence["mode"]}


def finalize_bench_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    finalized = deepcopy(evidence)
    finalized["evidence_contract"] = "serial-bench-evidence-v1"
    finalized["evidence_payload_sha256"] = evidence_payload_sha256(finalized)
    validate_bench_evidence(finalized)
    return finalized
