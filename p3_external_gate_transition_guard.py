"""Dry-run transition guard for the external validation gate lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from external_validation_package import ExternalValidationPackageError, GateEvidence, default_pilot_package
from p3_external_gate_status_reconciliation import reconcile_external_gates


SAFE_TIMESTAMP = "2026-08-22T17:30:00+00:00"
SAFE_EVIDENCE_CLASS = "SOFTWARE_VERIFIED"
EXPECTED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}


class ExternalGateTransitionError(ValueError):
    """Raised when the dry-run transition contract cannot be evaluated safely."""


def _evidence(ref: str) -> GateEvidence:
    return GateEvidence(ref, SAFE_EVIDENCE_CLASS, SAFE_TIMESTAMP)


def _simulate_transition_lifecycle() -> dict[str, Any]:
    package = default_pilot_package()
    blocked_submission_refused = False
    empty_reopen_refused = False

    package.submit_evidence("GV-02", "P2_004_ZERO_PII_REVIEW.md", SAFE_EVIDENCE_CLASS)
    package.block_gate("GV-06", "Physical COM-port and loopback evidence remain unverified")
    try:
        package.gates["GV-06"].submit_evidence(_evidence("P2_002_SERIAL_SOFTWARE_PROFILE.md"))
    except ExternalValidationPackageError as exc:
        blocked_submission_refused = str(exc) == "blocked_gate_requires_reopen"
    try:
        package.reopen_gate("GV-06", "")
    except ExternalValidationPackageError as exc:
        empty_reopen_refused = str(exc) == "reopen_reason_required"
    package.reopen_gate("GV-06", "Approved dry-run transition rehearsal only")
    package.submit_evidence("GV-06", "P2_002_SERIAL_SOFTWARE_PROFILE.md", SAFE_EVIDENCE_CLASS)
    package.block_gate("GV-09", "Staff training and manual fallback evidence remain externally unverified")

    summary = package.readiness_summary()
    return {
        "gate_statuses": {gate_id: gate.status for gate_id, gate in sorted(package.gates.items())},
        "gate_blockers": {gate_id: gate.blocker for gate_id, gate in sorted(package.gates.items()) if gate.blocker},
        "summary": summary,
        "blocked_submission_refused": blocked_submission_refused,
        "empty_reopen_refused": empty_reopen_refused,
        "reopened_gate_submitted": package.gates["GV-06"].status == "EVIDENCE_SUBMITTED",
        "evidence_submitted_is_not_passed": all(
            gate.status != "PASSED" for gate in package.gates.values()
        ),
        "external_owner_appointment": summary["external_owner_appointment"],
        "real_world_authorization": summary["real_world_authorization"],
        "clinical_validation_authorized": summary["clinical_validation_authorized"],
        "production_authorized": summary["production_authorized"],
        "runtime_authority": summary["runtime_authority"],
        "execution_status": summary["execution_status"],
        "clinical_governance_required": summary["clinical_governance_required"],
    }


def evaluate_transition_guard() -> dict[str, Any]:
    current = reconcile_external_gates()
    lifecycle = _simulate_transition_lifecycle()
    checks: dict[str, bool] = {}
    remediation_codes: list[str] = []

    checks["current_status_reconciled"] = (
        current.get("decision") == "P3_EXTERNAL_GATE_STATUS_RECONCILED"
        and current.get("status_counts") == {"BLOCKED": 7, "OPEN": 3, "EVIDENCE_SUBMITTED": 0, "TOTAL": 10}
        and current.get("ready_for_external_review") is False
    )
    if not checks["current_status_reconciled"]:
        remediation_codes.append("CURRENT_GATE_STATUS_NOT_RECONCILED")
    statuses = lifecycle["gate_statuses"]
    summary = lifecycle["summary"]
    checks["dry_run_transition_counts_bounded"] = summary.get("status_counts") == {
        "OPEN": 7,
        "EVIDENCE_SUBMITTED": 2,
        "BLOCKED": 1,
    } and summary.get("gate_count") == 10
    if not checks["dry_run_transition_counts_bounded"]:
        remediation_codes.append("TRANSITION_COUNT_MISMATCH")
    checks["blocked_gate_requires_reopen_before_submit"] = lifecycle["blocked_submission_refused"] is True
    if not checks["blocked_gate_requires_reopen_before_submit"]:
        remediation_codes.append("BLOCKED_GATE_SUBMISSION_BYPASS")
    checks["reopen_requires_nonempty_reason"] = lifecycle["empty_reopen_refused"] is True
    if not checks["reopen_requires_nonempty_reason"]:
        remediation_codes.append("REOPEN_REASON_BYPASS")
    checks["reopen_then_submit_is_explicit"] = (
        statuses.get("GV-06") == "EVIDENCE_SUBMITTED"
        and lifecycle["reopened_gate_submitted"] is True
    )
    if not checks["reopen_then_submit_is_explicit"]:
        remediation_codes.append("EXPLICIT_TRANSITION_NOT_RECORDED")
    checks["evidence_submission_is_not_pass"] = lifecycle["evidence_submitted_is_not_passed"] is True
    if not checks["evidence_submission_is_not_pass"]:
        remediation_codes.append("EVIDENCE_STATUS_PROMOTED_TO_PASS")
    checks["blocked_gate_reason_present"] = (
        statuses.get("GV-09") == "BLOCKED"
        and isinstance(lifecycle["gate_blockers"].get("GV-09"), str)
        and bool(lifecycle["gate_blockers"]["GV-09"].strip())
    )
    if not checks["blocked_gate_reason_present"]:
        remediation_codes.append("BLOCKED_GATE_REASON_MISSING")
    checks["boundary_locked"] = (
        lifecycle["real_world_authorization"] is False
        and lifecycle["clinical_validation_authorized"] is False
        and lifecycle["production_authorized"] is False
        and lifecycle["runtime_authority"] == "NONE"
        and lifecycle["execution_status"] == "NOT_STARTED"
        and lifecycle["clinical_governance_required"] is True
    )
    if not checks["boundary_locked"]:
        remediation_codes.append("TRANSITION_AUTHORIZATION_BOUNDARY_MUTATED")
    checks["lifecycle_text_redacted"] = not any(
        marker.lower() in json.dumps(lifecycle, ensure_ascii=True, sort_keys=True).lower()
        for marker in ("hn-", "an-", "mrn", "patient_id", "patient_token", "private key", "bearer ", "password", "api_key", "@")
    )
    if not checks["lifecycle_text_redacted"]:
        remediation_codes.append("TRANSITION_EVIDENCE_REDACTION_FAILED")

    remediation_codes = sorted(set(remediation_codes))
    decision = "P3_EXTERNAL_GATE_TRANSITION_GUARD_VERIFIED" if all(checks.values()) else "P3_EXTERNAL_GATE_TRANSITION_GUARD_BLOCKED"
    return {
        "schema_version": "p3-external-gate-transition-guard-v1",
        "evidence_type": "P3_EXTERNAL_GATE_TRANSITION_GUARD",
        "decision": decision,
        "checks": checks,
        "remediation_codes": remediation_codes,
        "current_external_status_counts": current.get("status_counts"),
        "current_external_blocked_gate_ids": current.get("blocked_gate_ids"),
        "current_external_open_gate_ids": current.get("open_gate_ids"),
        "dry_run_transition": lifecycle,
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "ready_for_external_review": False,
        "read_only": True,
        "fixture_only": True,
        "external_submission_allowed": False,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "authorization_promoted": False,
        "production_ready": False,
        "clinical_validation": "PENDING",
        "hardware_evidence": "UNVERIFIED",
        "claim_boundary": "CONTROLLED_PRODUCTION_PROTOTYPE",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_transition_guard(), ensure_ascii=True, indent=2, sort_keys=True))
