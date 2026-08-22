"""Read-back and decision guard for the independent-reviewer handoff boundary.

The control exercises only non-authorizing software fixtures. It proves that a
read-back may be accepted as unverified, stale responses are rejected, and even
an externally attributed status update cannot promote local authority.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from external_decision_lifecycle import (
    BLOCKED_SIMULATION,
    DecisionLifecycle,
    DecisionLifecycleError,
    PENDING_EXTERNAL_VERIFICATION,
    STALE_RESPONSE_REJECTED,
)
from external_decision_record import template as decision_record_template, validate as validate_decision_record
from p4_independent_reviewer_appointment_plan import evaluate_appointment_plan
from p4_independent_reviewer_handoff_readiness import evaluate_reviewer_handoff_readiness


ROOT = Path(__file__).resolve().parent
DECISION_RECORD_PATH = Path("evals/micro_rag/evidence/external-decision-record-local-20260821.json")
LOCKED_AUTHORIZATION = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}


class ReadbackGuardError(ValueError):
    """Raised when read-back evidence violates the local safety contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReadbackGuardError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadbackGuardError(f"cannot load {path}") from exc
    _require(isinstance(value, dict), f"{path} must contain an object")
    return value


def _fixture_received_record() -> dict[str, Any]:
    now = datetime(2026, 8, 22, 18, 15, tzinfo=timezone.utc)
    record = decision_record_template()
    record.update(
        {
            "record_id": "artifact:fixture-readback-record-01",
            "decision_id": "decision:fixture-readback-01",
            "submission_id": "submission:fixture-readback-01",
            "manifest_sha256": "a" * 64,
            "scope_id": "scope:fixture-readback-01",
            "window_id": "window:fixture-readback-01",
            "decision": "BLOCKED",
            "decision_basis": {
                "evidence_ids": ["evidence:fixture-readback-01"],
                "finding_ids": ["finding:fixture-readback-01"],
                "residual_risk_ids": ["risk:fixture-readback-01"],
                "condition_ids": ["condition:fixture-readback-01"],
            },
            "decided_by_role": "independent_reviewer",
            "decided_by_ref": "role:fixture-independent-reviewer",
            "decision_timestamp": now.isoformat().replace("+00:00", "Z"),
            "effective_from": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "rollback_ref": "rollback:fixture-readback-01",
            "stop_authority_ref": "stop:fixture-readback-01",
            "signature_ref": "signature:fixture-readback-01",
            "independent_verification_ref": "witness:fixture-readback-01",
            "revocation_ref": "revocation:fixture-readback-01",
            "response_authenticity": {
                "verification_status": "EXTERNAL_VERIFIER_PENDING",
                "key_id_ref": "key:fixture-readback-01",
                "certificate_ref": "certificate:fixture-readback-01",
                "trust_chain_ref": "trust:fixture-readback-01",
                "verified_at_utc": now.isoformat().replace("+00:00", "Z"),
            },
            "status": "EXTERNAL_DECISION_RECORD_RECEIVED",
            "evidence_class": "EXTERNAL_UNVERIFIED",
        }
    )
    return record


def _validate_local_decision_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "authorization_boundary", "authorization_promoted", "clinical_validation_authorized", "decision",
        "evidence_class", "external_decision_verified", "external_execution_authorized", "next_action",
        "production_authorized", "project", "repository", "schema_version", "status", "template_sha256", "validation",
    }
    if set(payload) != required:
        return {"valid": False, "error": "snapshot fields mismatch"}
    boundary = payload.get("authorization_boundary")
    validation = payload.get("validation")
    valid = (
        payload.get("schema_version") == "external-decision-record-v1"
        and payload.get("project") == "smart-ward-hub"
        and payload.get("repository") == "icezingza/smart-ward-hub"
        and payload.get("status") == "DECISION_RECORD_TEMPLATE"
        and payload.get("evidence_class") == "LOCAL_TEMPLATE"
        and payload.get("decision") == "PENDING_EXTERNAL_APPOINTMENT"
        and payload.get("external_decision_verified") is False
        and payload.get("authorization_promoted") is False
        and payload.get("external_execution_authorized") is False
        and payload.get("production_authorized") is False
        and payload.get("clinical_validation_authorized") is False
        and isinstance(payload.get("template_sha256"), str)
        and len(payload["template_sha256"]) == 64
        and all(character in "0123456789abcdef" for character in payload["template_sha256"])
        and boundary == LOCKED_AUTHORIZATION
        and isinstance(validation, dict)
        and validation.get("valid") is True
        and validation.get("mode") == "TEMPLATE_ONLY"
        and validation.get("decision_record_ready") is False
        and validation.get("external_decision_verified") is False
        and validation.get("authorization_promoted") is False
    )
    return {"valid": valid, "mode": "TEMPLATE_SNAPSHOT" if valid else "INVALID"}


def _response(*, decision_id: str, revision: int, status: str, observed_at: datetime) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "source_revision": revision,
        "source_event_hash": ("b" if revision == 0 else "c") * 64,
        "source_status": status,
        "observed_at_utc": observed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "clock_source_ref": "clock:fixture-readback-01",
    }


def evaluate_readback_guard() -> dict[str, Any]:
    now = datetime(2026, 8, 22, 18, 15, tzinfo=timezone.utc)
    local_record = _load_json(ROOT / DECISION_RECORD_PATH)
    local_validation = _validate_local_decision_snapshot(local_record)
    appointment = evaluate_appointment_plan()
    handoff = evaluate_reviewer_handoff_readiness()
    fixture = _fixture_received_record()
    fixture_validation = validate_decision_record(fixture)
    lifecycle = DecisionLifecycle(fixture, now=now)
    accepted = lifecycle.poll(_response(decision_id=lifecycle.decision_id, revision=0, status="PENDING_EXTERNAL_VERIFICATION", observed_at=now - timedelta(seconds=1)), now=now)
    stale = lifecycle.poll(_response(decision_id=lifecycle.decision_id, revision=0, status="PENDING_EXTERNAL_VERIFICATION", observed_at=now - timedelta(seconds=301)), now=now)
    update = lifecycle.apply_external_update(
        _response(decision_id=lifecycle.decision_id, revision=1, status="BLOCKED", observed_at=now),
        now=now,
        reason_ref="reason:fixture-external-block",
        actor_role="external_authority",
    )
    unauthorized_error = None
    try:
        lifecycle.apply_external_update(
            _response(decision_id=lifecycle.decision_id, revision=2, status="REQUIRES_CLARIFICATION", observed_at=now),
            now=now,
            reason_ref="reason:fixture-local-attempt",
            actor_role="local_evaluator",
        )
    except DecisionLifecycleError as exc:
        unauthorized_error = str(exc)
    status = lifecycle.status(now=now)
    checks = {
        "local_decision_record_template_valid": local_validation.get("valid") is True and local_validation.get("mode") == "TEMPLATE_SNAPSHOT",
        "fixture_received_record_valid": fixture_validation.get("valid") is True and fixture_validation.get("external_decision_verified") is False,
        "appointment_plan_still_template_only": appointment.get("decision") == "P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_READY" and appointment.get("appointment_confirmed") is False and appointment.get("submission_allowed") is False,
        "reviewer_handoff_still_appointment_only": handoff.get("decision") == "P4_INDEPENDENT_REVIEWER_HANDOFF_READY" and handoff.get("ready_for_external_review") is False,
        "fresh_poll_is_unverified": accepted.get("result") == "POLL_ACCEPTED_UNVERIFIED" and accepted.get("trusted") is False and accepted.get("external_decision_verified") is False and accepted.get("authorization_promoted") is False,
        "stale_poll_rejected": stale.get("result") == STALE_RESPONSE_REJECTED and stale.get("trusted") is False and stale.get("authorization_promoted") is False,
        "external_update_remains_non_authorizing": update.get("state") == BLOCKED_SIMULATION and update.get("external_decision_verified") is False and update.get("authorization_promoted") is False,
        "local_update_rejected": isinstance(unauthorized_error, str) and "external update actor must be external" in unauthorized_error,
        "audit_chain_valid": lifecycle.audit_chain_valid(),
        "boundary_locked": status.get("authorization_boundary") == LOCKED_AUTHORIZATION and status.get("production_authorized") is False and status.get("clinical_validation_authorized") is False and status.get("external_execution_authorized") is False,
    }
    remediation_codes = sorted({name.upper() for name, passed in checks.items() if not passed})
    decision = "P4_REVIEWER_READBACK_GUARD_VERIFIED" if all(checks.values()) else "P4_REVIEWER_READBACK_GUARD_BLOCKED"
    return {
        "schema_version": "p4-reviewer-readback-decision-guard-v1",
        "evidence_type": "P4_REVIEWER_READBACK_DECISION_GUARD",
        "decision": decision,
        "checks": checks,
        "remediation_codes": remediation_codes,
        "local_decision_record_source": DECISION_RECORD_PATH.as_posix(),
        "local_decision_record_validation": local_validation,
        "fixture_validation": fixture_validation,
        "fresh_poll_result": accepted,
        "stale_poll_result": stale,
        "external_update_result": update,
        "unauthorized_local_update_rejected": unauthorized_error is not None,
        "post_update_status": status,
        "audit_event_count": len(lifecycle.snapshot()["events"]),
        "appointment_plan_decision": appointment.get("decision"),
        "reviewer_handoff_decision": handoff.get("decision"),
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "reviewer_appointment": "PENDING_EXTERNAL_APPOINTMENT",
        "external_decision": "NOT_ISSUED",
        "independent_review_status": "NOT_STARTED",
        "appointment_confirmed": False,
        "ready_for_external_appointment": True if all(checks.values()) else False,
        "ready_for_external_review": False,
        "submission_allowed": False,
        "read_only": True,
        "fixture_only": True,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "authorization_promoted": False,
        "production_ready": False,
        "clinical_validation": "PENDING",
        "hardware_evidence": "UNVERIFIED",
        "claim_boundary": "CONTROLLED_PRODUCTION_PROTOTYPE",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_readback_guard(), ensure_ascii=True, indent=2, sort_keys=True))
