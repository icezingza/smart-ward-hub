"""Evidence-bounded reconciliation of the ten current external validation gates."""
from __future__ import annotations

from html import unescape
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from external_validation_package import default_pilot_package


ROOT = Path(__file__).resolve().parent
MATRIX_PATH = Path("controlled_pilot_presentation_deck/slide_04_external_gate_matrix.html")
BLOCKER_PATH = Path("evals/micro_rag/evidence/controlled-pilot-blocker-analysis-20260820.json")
FREEZE_PATH = Path("evals/micro_rag/evidence/release-candidate-freeze-20260820.json")
ROW_RE = re.compile(r"<tr\b[^>]*>(?P<row>.*?)</tr>", re.IGNORECASE | re.DOTALL)
CELL_RE = re.compile(r"<td\b[^>]*>(?P<cell>.*?)</td>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
STATUS_RE = re.compile(r"\b(BLOCKED|OPEN|EVIDENCE_SUBMITTED)\b", re.IGNORECASE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RAW_ID_RE = re.compile(r"\b(?:HN|AN|MRN|NATIONAL[_ -]?ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b", re.IGNORECASE)
SECRET_RE = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|api_key)\s*[:=]\s*\S+)", re.IGNORECASE)

EXPECTED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
EXPECTED_STATUS_COUNTS = {"BLOCKED": 7, "OPEN": 3, "EVIDENCE_SUBMITTED": 0}


class ExternalGateReconciliationError(ValueError):
    """Raised when a gate source cannot be parsed or reconciled safely."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExternalGateReconciliationError(f"cannot load {path}") from exc
    if not isinstance(value, dict):
        raise ExternalGateReconciliationError(f"{path} must contain an object")
    return value


def _clean_html(value: str) -> str:
    return " ".join(unescape(TAG_RE.sub("", value)).split())


def _parse_matrix(path: Path) -> dict[str, dict[str, str]]:
    try:
        html = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExternalGateReconciliationError(f"cannot load {path}") from exc
    parsed: dict[str, dict[str, str]] = {}
    for match in ROW_RE.finditer(html):
        cells = [_clean_html(cell.group("cell")) for cell in CELL_RE.finditer(match.group("row"))]
        if len(cells) != 5:
            continue
        gate_match = re.fullmatch(r"GV-(?:0[1-9]|10)", cells[0])
        status_match = STATUS_RE.search(cells[3])
        if not gate_match or not status_match:
            continue
        parsed[cells[0]] = {
            "domain": cells[1],
            "owner_role": cells[2],
            "status": status_match.group(1).upper(),
            "evidence_and_blocker": cells[4],
        }
    if len(parsed) != 10:
        raise ExternalGateReconciliationError(f"expected 10 gate rows, found {len(parsed)}")
    return parsed


def _sha256(path: Path) -> str:
    raw = path.read_bytes()
    if path.suffix.lower() in {".csv", ".css", ".example", ".html", ".ini", ".js", ".json", ".mako", ".md", ".py", ".sh", ".sql", ".svg", ".toml", ".txt", ".xml", ".yaml", ".yml"} or path.name in {".gitignore"}:
        raw = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _freeze_hash(freeze: dict[str, Any], relative: Path) -> str | None:
    files = freeze.get("files")
    if not isinstance(files, list):
        return None
    for entry in files:
        if isinstance(entry, dict) and entry.get("path") == relative.as_posix():
            value = entry.get("sha256")
            return value if isinstance(value, str) else None
    return None


def _safe_evidence_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return not RAW_ID_RE.search(value) and not SECRET_RE.search(value) and "@" not in value


def _normalized_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def reconcile_external_gates(*, root: Path = ROOT) -> dict[str, Any]:
    package = default_pilot_package()
    matrix = _parse_matrix(root / MATRIX_PATH)
    blocker_report = _load_json(root / BLOCKER_PATH)
    freeze = _load_json(root / FREEZE_PATH)
    registry_ids = sorted(package.gates)
    matrix_ids = sorted(matrix)
    blockers = blocker_report.get("blockers")
    if not isinstance(blockers, list):
        raise ExternalGateReconciliationError("blocker report must contain blockers list")
    blocker_by_id = {item.get("gate_id"): item for item in blockers if isinstance(item, dict)}
    checks: dict[str, bool] = {}
    remediation_codes: list[str] = []

    checks["registry_has_exactly_ten_gates"] = registry_ids == [f"GV-{index:02d}" for index in range(1, 11)]
    if not checks["registry_has_exactly_ten_gates"]:
        remediation_codes.append("GATE_REGISTRY_INCOMPLETE")
    checks["matrix_has_exactly_ten_gates"] = matrix_ids == registry_ids
    if not checks["matrix_has_exactly_ten_gates"]:
        remediation_codes.append("GATE_MATRIX_INCOMPLETE")

    gate_records: list[dict[str, Any]] = []
    for gate_id in registry_ids:
        gate = package.gates[gate_id]
        current = matrix.get(gate_id, {})
        blocker = blocker_by_id.get(gate_id)
        status = current.get("status")
        record: dict[str, Any] = {
            "gate_id": gate_id,
            "domain": gate.domain,
            "owner_role": gate.owner_role,
            "status": status,
            "required_evidence": list(gate.required_evidence),
            "matrix_summary": current.get("evidence_and_blocker"),
        }
        if status == "BLOCKED":
            record.update(
                {
                    "blocker_id": blocker.get("blocker_id") if blocker else None,
                    "blocker_reason": blocker.get("blocker_reason") if blocker else None,
                    "external_action": blocker.get("external_action") if blocker else None,
                    "external_evidence_status": blocker.get("external_evidence_status") if blocker else None,
                    "software_evidence_available": blocker.get("software_evidence_available") if blocker else None,
                    "severity": blocker.get("severity") if blocker else None,
                    "priority": blocker.get("priority") if blocker else None,
                    "stop_condition": blocker.get("stop_condition") if blocker else None,
                }
            )
        gate_records.append(record)

    blocked_ids = sorted(gate_id for gate_id, current in matrix.items() if current["status"] == "BLOCKED")
    open_ids = sorted(gate_id for gate_id, current in matrix.items() if current["status"] == "OPEN")
    submitted_ids = sorted(gate_id for gate_id, current in matrix.items() if current["status"] == "EVIDENCE_SUBMITTED")
    checks["status_counts_match_locked_summary"] = {
        "BLOCKED": len(blocked_ids),
        "OPEN": len(open_ids),
        "EVIDENCE_SUBMITTED": len(submitted_ids),
    } == EXPECTED_STATUS_COUNTS
    if not checks["status_counts_match_locked_summary"]:
        remediation_codes.append("GATE_STATUS_COUNT_MISMATCH")
    checks["blocked_ids_match_blocker_report"] = blocked_ids == sorted(blocker_by_id) and len(blocker_by_id) == 7
    if not checks["blocked_ids_match_blocker_report"]:
        remediation_codes.append("BLOCKER_SET_MISMATCH")
    checks["blocked_records_have_external_blocker_fields"] = all(
        isinstance(blocker_by_id.get(gate_id), dict)
        and blocker_by_id[gate_id].get("status") == "BLOCKED"
        and blocker_by_id[gate_id].get("external_evidence_status") == "NOT_VERIFIED"
        and blocker_by_id[gate_id].get("reopen_required_before_new_submission") is True
        and isinstance(blocker_by_id[gate_id].get("required_external_evidence"), list)
        and isinstance(blocker_by_id[gate_id].get("stop_condition"), str)
        for gate_id in blocked_ids
    )
    if not checks["blocked_records_have_external_blocker_fields"]:
        remediation_codes.append("BLOCKER_RECORD_INCOMPLETE")
    checks["registry_domain_owner_evidence_matches_matrix"] = all(
        _normalized_label(gate.domain) in _normalized_label(matrix[gate_id]["domain"])
        for gate_id, gate in package.gates.items()
    )
    if not checks["registry_domain_owner_evidence_matches_matrix"]:
        remediation_codes.append("GATE_REGISTRY_MATRIX_MISMATCH")
    checks["all_gate_text_is_redacted"] = all(
        _safe_evidence_text(json.dumps(record, ensure_ascii=True, sort_keys=True)) for record in gate_records
    )
    if not checks["all_gate_text_is_redacted"]:
        remediation_codes.append("GATE_STATUS_REDACTION_FAILED")

    checks["blocker_report_summary_matches_matrix"] = blocker_report.get("gate_summary") == {
        "blocked": 7,
        "evidence_submitted": 0,
        "open": 3,
        "total": 10,
    }
    if not checks["blocker_report_summary_matches_matrix"]:
        remediation_codes.append("BLOCKER_SUMMARY_MISMATCH")
    checks["authorization_boundary_locked"] = (
        blocker_report.get("clinical_validation_authorized") is False
        and blocker_report.get("production_authorized") is False
        and blocker_report.get("runtime_authority") == "NONE"
        and blocker_report.get("operations_state") == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    )
    if not checks["authorization_boundary_locked"]:
        remediation_codes.append("EXTERNAL_GATE_AUTHORIZATION_BOUNDARY_MUTATED")
    checks["freeze_status_pass"] = freeze.get("freeze_status") == "PASS"
    if not checks["freeze_status_pass"]:
        remediation_codes.append("FREEZE_NOT_PASS")
    matrix_expected_hash = _freeze_hash(freeze, MATRIX_PATH)
    blocker_expected_hash = _freeze_hash(freeze, BLOCKER_PATH)
    checks["matrix_bound_to_freeze"] = matrix_expected_hash == _sha256(root / MATRIX_PATH)
    if not checks["matrix_bound_to_freeze"]:
        remediation_codes.append("GATE_MATRIX_FREEZE_HASH_MISMATCH")
    checks["blocker_report_bound_to_freeze"] = blocker_expected_hash == _sha256(root / BLOCKER_PATH)
    if not checks["blocker_report_bound_to_freeze"]:
        remediation_codes.append("BLOCKER_REPORT_FREEZE_HASH_MISMATCH")

    remediation_codes = sorted(set(remediation_codes))
    decision = "P3_EXTERNAL_GATE_STATUS_RECONCILED" if all(checks.values()) else "P3_EXTERNAL_GATE_STATUS_RECONCILIATION_BLOCKED"
    return {
        "schema_version": "p3-external-gate-status-reconciliation-v1",
        "evidence_type": "P3_EXTERNAL_GATE_STATUS_RECONCILIATION",
        "decision": decision,
        "checks": checks,
        "remediation_codes": remediation_codes,
        "status_counts": {
            "BLOCKED": len(blocked_ids),
            "OPEN": len(open_ids),
            "EVIDENCE_SUBMITTED": len(submitted_ids),
            "TOTAL": len(matrix),
        },
        "blocked_gate_ids": blocked_ids,
        "open_gate_ids": open_ids,
        "evidence_submitted_gate_ids": submitted_ids,
        "gate_records": gate_records,
        "external_gate_registry_source": "external_validation_package.default_pilot_package",
        "current_status_matrix_source": MATRIX_PATH.as_posix(),
        "blocker_analysis_source": BLOCKER_PATH.as_posix(),
        "freeze_source_revision": freeze.get("source_revision"),
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "ready_for_external_review": False,
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
    print(json.dumps(reconcile_external_gates(), ensure_ascii=True, indent=2, sort_keys=True))
