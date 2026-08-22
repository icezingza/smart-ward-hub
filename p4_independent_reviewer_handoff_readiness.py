"""Evidence-bounded readiness control for an independent-reviewer handoff."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from independent_reviewer_readiness_preflight import validate_preflight
from p4_blocked_gate_unblock_readiness import evaluate_p4_blocked_gate_readiness


ROOT = Path(__file__).resolve().parent
PREFLIGHT_PATH = Path("evals/micro_rag/evidence/independent-reviewer-readiness-preflight-local-20260821.json")
FREEZE_PATH = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")
EXPECTED_STATUS_COUNTS = {
    "PENDING_EXTERNAL": 8,
    "SOFTWARE_VERIFIED_PENDING_READBACK": 3,
    "SOFTWARE_LOCKED_EXTERNAL_REVIEW_PENDING": 1,
}
RAW_ID_RE = re.compile(r"\b(?:HN|AN|MRN|NATIONAL[_ -]?ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b", re.IGNORECASE)
SECRET_RE = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|api_key)\s*[:=]\s*\S+)", re.IGNORECASE)


class ReviewerHandoffReadinessError(ValueError):
    """Raised when local reviewer-handoff evidence is incomplete or unsafe."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewerHandoffReadinessError(f"cannot load {path}") from exc
    if not isinstance(value, dict):
        raise ReviewerHandoffReadinessError(f"{path} must contain an object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _freeze_hash(freeze: dict[str, Any], relative_path: str) -> str | None:
    files = freeze.get("files")
    if not isinstance(files, list):
        return None
    for item in files:
        if isinstance(item, dict) and item.get("path") == relative_path:
            value = item.get("sha256")
            return value if isinstance(value, str) else None
    return None


def _redacted(value: Any) -> bool:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True)
    return not RAW_ID_RE.search(encoded) and not SECRET_RE.search(encoded) and "@" not in encoded


def evaluate_reviewer_handoff_readiness(*, root: Path = ROOT) -> dict[str, Any]:
    preflight = _load_json(root / PREFLIGHT_PATH)
    freeze = _load_json(root / FREEZE_PATH)
    blocked = evaluate_p4_blocked_gate_readiness(root=root)
    checks: dict[str, bool] = {}
    remediation_codes: list[str] = []

    try:
        validation = validate_preflight(preflight, template_only=False)
        preflight_valid = validation.get("valid") is True
    except Exception as exc:  # validator errors are normalized to a blocked decision
        validation = {"error": type(exc).__name__}
        preflight_valid = False
    checks["preflight_schema_valid"] = preflight_valid
    if not checks["preflight_schema_valid"]:
        remediation_codes.append("REVIEWER_PREFLIGHT_INVALID")
    checklist = preflight.get("reviewer_checklist")
    pending = preflight.get("external_inputs_pending")
    checks["twelve_item_checklist_complete"] = isinstance(checklist, list) and len(checklist) == 12 and len({item.get("check_id") for item in checklist if isinstance(item, dict)}) == 12
    if not checks["twelve_item_checklist_complete"]:
        remediation_codes.append("REVIEWER_CHECKLIST_INCOMPLETE")
    checks["twenty_two_artifacts_bound"] = preflight.get("artifact_count") == 22 and preflight.get("mapping_count") == 12
    if not checks["twenty_two_artifacts_bound"]:
        remediation_codes.append("REVIEWER_ARTIFACT_MAPPING_INCOMPLETE")
    status_counts: dict[str, int] = {}
    if isinstance(checklist, list):
        for item in checklist:
            if isinstance(item, dict) and isinstance(item.get("status"), str):
                status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1
    checks["checklist_status_counts_match"] = status_counts == EXPECTED_STATUS_COUNTS
    if not checks["checklist_status_counts_match"]:
        remediation_codes.append("REVIEWER_CHECKLIST_STATUS_COUNT_MISMATCH")
    checks["external_appointment_boundary_locked"] = (
        preflight.get("status") == "REVIEWER_PRECHECK_READY_FOR_EXTERNAL_APPOINTMENT"
        and preflight.get("submission_status") == "NOT_SUBMITTED"
        and preflight.get("reviewer_appointment") == "PENDING_EXTERNAL_APPOINTMENT"
        and preflight.get("external_decision") == "NOT_ISSUED"
        and preflight.get("package_state") == "READY_FOR_EXTERNAL_OWNER_APPOINTMENT"
        and preflight.get("wave_e_bundle_state") == "NOT_EXECUTED"
        and preflight.get("independent_review_status") == "NOT_STARTED"
    )
    if not checks["external_appointment_boundary_locked"]:
        remediation_codes.append("REVIEWER_APPOINTMENT_BOUNDARY_MUTATED")
    checks["pending_external_inputs_complete"] = isinstance(pending, list) and len(pending) == 12 and all(isinstance(item, str) and item.strip() for item in pending)
    if not checks["pending_external_inputs_complete"]:
        remediation_codes.append("EXTERNAL_INPUT_REGISTER_INCOMPLETE")
    checks["local_software_only_locked"] = (
        preflight.get("software_evidence_only") is True
        and preflight.get("independent_verification_required") is True
        and preflight.get("redaction") == "PASS"
        and preflight.get("raw_identity_present") is False
    )
    if not checks["local_software_only_locked"]:
        remediation_codes.append("REVIEWER_SOFTWARE_ONLY_BOUNDARY_MUTATED")
    checks["authorization_boundary_locked"] = preflight.get("authorization_boundary") == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    if not checks["authorization_boundary_locked"]:
        remediation_codes.append("REVIEWER_AUTHORIZATION_BOUNDARY_MUTATED")
    checks["blocked_gate_dependency_reconciled"] = blocked.get("decision") == "P4_BLOCKED_GATE_UNBLOCK_READINESS_RECONCILED" and blocked.get("status_counts") == {"BLOCKED": 7, "EVIDENCE_SUBMITTED": 0, "OPEN": 3, "TOTAL": 10}
    if not checks["blocked_gate_dependency_reconciled"]:
        remediation_codes.append("BLOCKED_GATE_DEPENDENCY_NOT_RECONCILED")
    preflight_hash = _freeze_hash(freeze, PREFLIGHT_PATH.as_posix())
    checks["preflight_freeze_bound"] = isinstance(preflight_hash, str) and preflight_hash == _sha256(root / PREFLIGHT_PATH)
    if not checks["preflight_freeze_bound"]:
        remediation_codes.append("REVIEWER_PREFLIGHT_FREEZE_BINDING_MISSING")
    checks["freeze_pass"] = freeze.get("freeze_status") == "PASS"
    if not checks["freeze_pass"]:
        remediation_codes.append("REVIEWER_HANDOFF_FREEZE_NOT_PASS")
    checks["preflight_redacted"] = _redacted(preflight)
    if not checks["preflight_redacted"]:
        remediation_codes.append("REVIEWER_PREFLIGHT_REDACTION_FAILED")

    remediation_codes = sorted(set(remediation_codes))
    decision = "P4_INDEPENDENT_REVIEWER_HANDOFF_READY" if all(checks.values()) else "P4_INDEPENDENT_REVIEWER_HANDOFF_BLOCKED"
    return {
        "schema_version": "p4-independent-reviewer-handoff-readiness-v1",
        "evidence_type": "P4_INDEPENDENT_REVIEWER_HANDOFF_READINESS",
        "decision": decision,
        "checks": checks,
        "remediation_codes": remediation_codes,
        "preflight_validation": validation,
        "preflight_source": PREFLIGHT_PATH.as_posix(),
        "freeze_source": FREEZE_PATH.as_posix(),
        "preflight_status": preflight.get("status"),
        "submission_status": preflight.get("submission_status"),
        "reviewer_appointment": preflight.get("reviewer_appointment"),
        "external_decision": preflight.get("external_decision"),
        "independent_review_status": preflight.get("independent_review_status"),
        "mapping_count": preflight.get("mapping_count"),
        "artifact_count": preflight.get("artifact_count"),
        "checklist_status_counts": status_counts,
        "external_inputs_pending_count": len(pending) if isinstance(pending, list) else 0,
        "external_gate_status_counts": blocked.get("status_counts"),
        "external_gate_blocked_ids": blocked.get("blocked_gate_ids"),
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "ready_for_external_appointment": True if all(checks.values()) else False,
        "ready_for_external_review": False,
        "submission_allowed": False,
        "read_only": True,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "authorization_promoted": False,
        "production_ready": False,
        "clinical_validation": "PENDING",
        "hardware_evidence": "UNVERIFIED",
        "claim_boundary": "CONTROLLED_PRODUCTION_PROTOTYPE",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_reviewer_handoff_readiness(), ensure_ascii=True, indent=2, sort_keys=True))
