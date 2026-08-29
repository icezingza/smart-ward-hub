"""Evidence-bounded readiness matrix for the seven blocked external gates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from p3_external_gate_status_reconciliation import (
    BLOCKER_PATH,
    ROOT,
    reconcile_external_gates,
)


FREEZE_PATH = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")
EXPECTED_BLOCKED = ["GV-01", "GV-03", "GV-04", "GV-06", "GV-07", "GV-08", "GV-09"]
RAW_ID_RE = re.compile(r"\b(?:HN|AN|MRN|NATIONAL[_ -]?ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b", re.IGNORECASE)
SECRET_RE = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|api_key)\s*[:=]\s*\S+)", re.IGNORECASE)


class P4BlockedGateReadinessError(ValueError):
    """Raised when blocked-gate readiness evidence is incomplete or unsafe."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise P4BlockedGateReadinessError(f"cannot load {path}") from exc
    if not isinstance(value, dict):
        raise P4BlockedGateReadinessError(f"{path} must contain an object")
    return value


def _redacted(value: Any) -> bool:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True)
    return not RAW_ID_RE.search(encoded) and not SECRET_RE.search(encoded) and "@" not in encoded


def _sha256(path: Path) -> str:
    raw = path.read_bytes()
    if path.suffix.lower() in {".csv", ".css", ".example", ".html", ".ini", ".js", ".json", ".mako", ".md", ".py", ".sh", ".sql", ".svg", ".toml", ".txt", ".xml", ".yaml", ".yml"} or path.name in {".gitattributes", ".gitignore"}:
        raw = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _freeze_hash(freeze: dict[str, Any], relative_path: str) -> str | None:
    files = freeze.get("files")
    if not isinstance(files, list):
        return None
    for item in files:
        if isinstance(item, dict) and item.get("path") == relative_path:
            value = item.get("sha256")
            return value if isinstance(value, str) else None
    return None


def evaluate_p4_blocked_gate_readiness(*, root: Path = ROOT) -> dict[str, Any]:
    current = reconcile_external_gates(root=root)
    blocker_report = _load_json(root / BLOCKER_PATH)
    freeze = _load_json(root / FREEZE_PATH)
    blocker_items = blocker_report.get("blockers")
    if not isinstance(blocker_items, list):
        raise P4BlockedGateReadinessError("blocker report list is missing")
    blockers = {item.get("gate_id"): item for item in blocker_items if isinstance(item, dict)}
    checks: dict[str, bool] = {}
    remediation_codes: list[str] = []

    checks["current_status_reconciled"] = (
        current.get("decision") == "P3_EXTERNAL_GATE_STATUS_RECONCILED"
        and current.get("blocked_gate_ids") == EXPECTED_BLOCKED
        and current.get("status_counts") == {"BLOCKED": 7, "OPEN": 3, "EVIDENCE_SUBMITTED": 0, "TOTAL": 10}
    )
    if not checks["current_status_reconciled"]:
        remediation_codes.append("CURRENT_EXTERNAL_STATUS_NOT_RECONCILED")
    checks["exactly_seven_blocker_records"] = sorted(blockers) == EXPECTED_BLOCKED and len(blockers) == 7
    if not checks["exactly_seven_blocker_records"]:
        remediation_codes.append("BLOCKED_GATE_RECORD_SET_MISMATCH")

    records: list[dict[str, Any]] = []
    for gate_id in EXPECTED_BLOCKED:
        item = blockers.get(gate_id)
        if not isinstance(item, dict):
            records.append({"gate_id": gate_id, "status": "MISSING"})
            continue
        required = item.get("required_external_evidence")
        software_evidence = item.get("software_evidence")
        record = {
            "gate_id": gate_id,
            "blocker_id": item.get("blocker_id"),
            "owner_role": item.get("owner_role"),
            "status": item.get("status"),
            "severity": item.get("severity"),
            "priority": item.get("priority"),
            "blocker_reason": item.get("blocker_reason"),
            "external_action": item.get("external_action"),
            "external_evidence_status": item.get("external_evidence_status"),
            "required_external_evidence": required,
            "software_evidence_available": item.get("software_evidence_available"),
            "software_evidence_refs": [
                evidence.get("ref")
                for evidence in software_evidence
                if isinstance(evidence, dict) and isinstance(evidence.get("ref"), str)
            ] if isinstance(software_evidence, list) else [],
            "reopen_required_before_new_submission": item.get("reopen_required_before_new_submission"),
            "stop_condition": item.get("stop_condition"),
            "unblock_status": "EXTERNAL_EVIDENCE_AND_OWNER_ACTION_PENDING",
            "local_software_evidence_does_not_unlock": True,
            "external_owner_or_external_validation_required": True,
        }
        records.append(record)

    checks["all_blocked_records_complete"] = all(
        record.get("status") == "BLOCKED"
        and isinstance(record.get("owner_role"), str)
        and isinstance(record.get("blocker_reason"), str)
        and isinstance(record.get("external_action"), str)
        and record.get("external_evidence_status") == "NOT_VERIFIED"
        and isinstance(record.get("required_external_evidence"), list)
        and len(record["required_external_evidence"]) >= 3
        and record.get("reopen_required_before_new_submission") is True
        and isinstance(record.get("stop_condition"), str)
        and record.get("unblock_status") == "EXTERNAL_EVIDENCE_AND_OWNER_ACTION_PENDING"
        and record.get("local_software_evidence_does_not_unlock") is True
        for record in records
    )
    if not checks["all_blocked_records_complete"]:
        remediation_codes.append("BLOCKED_GATE_UNBLOCK_CONDITION_INCOMPLETE")
    checks["all_records_redacted"] = _redacted(records)
    if not checks["all_records_redacted"]:
        remediation_codes.append("BLOCKED_GATE_REDACTION_FAILED")
    checks["blocker_summary_matches"] = blocker_report.get("gate_summary") == {
        "blocked": 7,
        "evidence_submitted": 0,
        "open": 3,
        "total": 10,
    }
    if not checks["blocker_summary_matches"]:
        remediation_codes.append("BLOCKER_SUMMARY_MISMATCH")
    checks["authorization_boundary_locked"] = (
        blocker_report.get("clinical_validation_authorized") is False
        and blocker_report.get("production_authorized") is False
        and blocker_report.get("runtime_authority") == "NONE"
        and blocker_report.get("operations_state") == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    )
    if not checks["authorization_boundary_locked"]:
        remediation_codes.append("P4_AUTHORIZATION_BOUNDARY_MUTATED")
    checks["freeze_pass"] = freeze.get("freeze_status") == "PASS"
    if not checks["freeze_pass"]:
        remediation_codes.append("P4_FREEZE_NOT_PASS")
    blocker_hash = _freeze_hash(freeze, BLOCKER_PATH.as_posix())
    checks["blocker_report_freeze_bound"] = isinstance(blocker_hash, str) and blocker_hash == _sha256(root / BLOCKER_PATH)
    if not checks["blocker_report_freeze_bound"]:
        remediation_codes.append("P4_BLOCKER_FREEZE_BINDING_MISSING")

    remediation_codes = sorted(set(remediation_codes))
    decision = "P4_BLOCKED_GATE_UNBLOCK_READINESS_RECONCILED" if all(checks.values()) else "P4_BLOCKED_GATE_UNBLOCK_READINESS_BLOCKED"
    return {
        "schema_version": "p4-blocked-gate-unblock-readiness-v1",
        "evidence_type": "P4_BLOCKED_EXTERNAL_GATE_UNBLOCK_READINESS",
        "decision": decision,
        "checks": checks,
        "remediation_codes": remediation_codes,
        "status_counts": current.get("status_counts"),
        "blocked_gate_ids": EXPECTED_BLOCKED,
        "records": records,
        "current_status_source": "p3_external_gate_status_reconciliation.py",
        "blocker_source": BLOCKER_PATH.as_posix(),
        "freeze_source": FREEZE_PATH.as_posix(),
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "ready_for_external_review": False,
        "unblock_authorized": False,
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
    print(json.dumps(evaluate_p4_blocked_gate_readiness(), ensure_ascii=True, indent=2, sort_keys=True))
