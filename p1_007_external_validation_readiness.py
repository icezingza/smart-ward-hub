from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "p1-007-external-validation-readiness-v1"
PROJECT = "smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|evidence|artifact|scope|window|incident|rollback|commit|freeze|protocol|review|retention|training|fallback|owner|gate):[A-Za-z0-9._-]+$")
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b", re.IGNORECASE)
RAW_CONTACT = re.compile(r"(?:@|\+?\d[\d\s().-]{6,}|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b)", re.IGNORECASE)
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)", re.IGNORECASE)
LOCKED_AUTHORIZATION = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
GATE_DEFINITIONS = {
    "GV-01": ("clinical_governance", "clinical_owner", ("approved_protocol", "consent_or_waiver", "signed_scope")),
    "GV-02": ("privacy_security", "privacy_security_reviewer", ("zero_pii_review", "retention_decision", "access_control_review")),
    "GV-03": ("his_admission", "integration_owner", ("real_his_transcript", "fhir_ack_reconciliation", "failure_recovery")),
    "GV-04": ("identity_transport", "security_owner", ("real_oidc_validation", "real_mtls_handshake", "key_rotation_transcript")),
    "GV-05": ("fixed_hub_host", "host_operator", ("acer_hardening_checklist", "firewall_acl_evidence", "service_recovery")),
    "GV-06": ("hardware_recovery", "reliability_owner", ("serial_loopback_s015", "power_loss_drill", "disk_full_drill")),
    "GV-07": ("forensic_anchor", "forensic_owner", ("external_worm_receipt", "trusted_timestamp", "cross_boundary_verify")),
    "GV-08": ("device_trust", "security_owner", ("manufacturer_provenance", "hardware_key_custody", "revocation_distribution")),
    "GV-09": ("clinical_operations", "ward_manager", ("staff_training", "manual_fallback_sop", "alarm_fatigue_review")),
    "GV-10": ("independent_review", "independent_reviewer", ("analysis_plan", "adjudication_plan", "audit_export")),
}


class ExternalValidationReadinessError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExternalValidationReadinessError(message)


def _opaque(value: Any, field: str, *, pending: bool = False) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    if pending and value == PENDING:
        return
    _require(OPAQUE_REF.fullmatch(value) is not None, f"{field} must be an opaque reference")
    _require(RAW_ID.search(value) is None and RAW_CONTACT.search(value) is None, f"{field} must not contain raw identity/contact")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")


def _safe_text(value: Any, field: str) -> None:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    _require(len(value) <= 512, f"{field} too large")
    _require(RAW_ID.search(value) is None and RAW_CONTACT.search(value) is None, f"{field} must not contain raw identity/contact")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")


def validate_manifest(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "manifest must be an object")
    allowed = {"schema_version", "project", "status", "gate_count", "gate_status_counts", "external_execution_status", "external_owner_appointment", "real_world_authorization", "clinical_validation_authorized", "production_authorized", "runtime_authority", "pilot_gate_status", "authorization_boundary", "coordination_evidence_only", "evidence_class", "claim_boundary", "reopen_policy", "blocker_policy", "gates", "package_ref", "scope_ref", "window_ref", "rollback_ref", "independent_verification_required"}
    unknown = sorted(set(payload) - allowed)
    _require(not unknown, f"unknown fields: {unknown}")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    _require(payload.get("status") == "COORDINATION_SOFTWARE_READY", "status must remain coordination software ready")
    _require(payload.get("gate_count") == 10, "gate_count must remain 10")
    _require(payload.get("gate_status_counts") == {"OPEN": 10, "EVIDENCE_SUBMITTED": 0, "BLOCKED": 0}, "initial gate status counts mismatch")
    _require(payload.get("external_execution_status") == "NOT_STARTED", "external execution must remain NOT_STARTED")
    _require(payload.get("external_owner_appointment") == PENDING, "external owner appointment must remain pending")
    _require(payload.get("real_world_authorization") is False, "real_world_authorization must remain false")
    _require(payload.get("clinical_validation_authorized") is False, "clinical_validation_authorized must remain false")
    _require(payload.get("production_authorized") is False, "production_authorized must remain false")
    _require(payload.get("runtime_authority") == "NONE", "runtime_authority must remain NONE")
    _require(payload.get("pilot_gate_status") == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION", "pilot gate must remain blocked")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("coordination_evidence_only") is True, "coordination_evidence_only must be true")
    _require(payload.get("evidence_class") == "COORDINATION_ARTIFACT_UNVERIFIED", "evidence class mismatch")
    _require(payload.get("claim_boundary") == "CONTROLLED_PROTOTYPE_SOFTWARE_EVIDENCE_ONLY_NO_EXTERNAL_AUTHORIZATION", "claim boundary mismatch")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")
    _opaque(payload.get("package_ref"), "package_ref", pending=template_only)
    _opaque(payload.get("scope_ref"), "scope_ref", pending=template_only)
    _opaque(payload.get("window_ref"), "window_ref", pending=template_only)
    _opaque(payload.get("rollback_ref"), "rollback_ref", pending=template_only)

    reopen_policy = payload.get("reopen_policy")
    _require(reopen_policy == {"blocked_gate_submission": "REJECT_UNTIL_REOPEN", "reopen_requires_reason": True, "reopen_clears_blocker": True}, "reopen policy mismatch")
    blocker_policy = payload.get("blocker_policy")
    _require(isinstance(blocker_policy, dict), "blocker_policy must be an object")
    _require(blocker_policy.get("blocked_count_visible") is True, "blocked count must remain visible")
    _require(blocker_policy.get("reason_required") is True, "blocker reason must be required")
    _require(blocker_policy.get("max_reason_length") == 240, "blocker reason length mismatch")
    _safe_text(blocker_policy.get("note"), "blocker_policy.note")

    gates = payload.get("gates")
    _require(isinstance(gates, dict) and set(gates) == set(GATE_DEFINITIONS), "gates must contain exactly GV-01 through GV-10")
    for gate_id, (domain, owner_role, required_evidence) in GATE_DEFINITIONS.items():
        gate = gates[gate_id]
        _require(isinstance(gate, dict), f"gates.{gate_id} must be an object")
        _require(gate.get("domain") == domain, f"gates.{gate_id}.domain mismatch")
        _require(gate.get("owner_role") == owner_role, f"gates.{gate_id}.owner_role mismatch")
        _require(gate.get("required_evidence") == list(required_evidence), f"gates.{gate_id}.required_evidence mismatch")
        _require(gate.get("status") == "OPEN", f"gates.{gate_id}.status must remain OPEN")
        _require(gate.get("blocker") is None, f"gates.{gate_id}.blocker must remain null")
        if template_only:
            _require(gate.get("evidence_refs") == [], f"gates.{gate_id}.evidence_refs must remain empty in template")
        else:
            _require(isinstance(gate.get("evidence_refs"), list), f"gates.{gate_id}.evidence_refs must be a list")
        _safe_text(gate.get("stop_condition"), f"gates.{gate_id}.stop_condition")
    return {"valid": True, "status": payload["status"], "gate_count": payload["gate_count"], "external_execution_status": payload["external_execution_status"], "real_world_authorization": payload["real_world_authorization"], "coordination_evidence_only": payload["coordination_evidence_only"]}


def template() -> dict[str, Any]:
    stop_conditions = {
        "GV-01": "Stop if clinical protocol, consent/waiver, signed scope or accountable clinical owner is missing.",
        "GV-02": "Stop on unresolved privacy leakage, retention ambiguity, unsafe access or export boundary.",
        "GV-03": "Stop if real HIS acknowledgment, FHIR reconciliation or failure recovery is not evidenced.",
        "GV-04": "Stop if real OIDC/mTLS, key rotation or transport identity evidence is absent.",
        "GV-05": "Stop if Acer account, firewall/ACL, patch, disk, service or host recovery evidence is absent.",
        "GV-06": "Stop if serial loopback, power-loss or disk-full evidence is absent or only simulated.",
        "GV-07": "Stop if independent WORM receipt, trusted timestamp or cross-boundary verification is absent.",
        "GV-08": "Stop if manufacturer provenance, hardware key custody or revocation distribution is absent.",
        "GV-09": "Stop if staff training, manual fallback or alarm-fatigue review is incomplete.",
        "GV-10": "Stop if analysis/adjudication plan or independent audit export is incomplete.",
    }
    gates = {}
    for gate_id, (domain, owner_role, required_evidence) in GATE_DEFINITIONS.items():
        gates[gate_id] = {"domain": domain, "owner_role": owner_role, "required_evidence": list(required_evidence), "status": "OPEN", "blocker": None, "evidence_refs": [], "stop_condition": stop_conditions[gate_id]}
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "status": "COORDINATION_SOFTWARE_READY",
        "gate_count": 10,
        "gate_status_counts": {"OPEN": 10, "EVIDENCE_SUBMITTED": 0, "BLOCKED": 0},
        "external_execution_status": "NOT_STARTED",
        "external_owner_appointment": PENDING,
        "real_world_authorization": False,
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "authorization_boundary": dict(LOCKED_AUTHORIZATION),
        "coordination_evidence_only": True,
        "evidence_class": "COORDINATION_ARTIFACT_UNVERIFIED",
        "claim_boundary": "CONTROLLED_PROTOTYPE_SOFTWARE_EVIDENCE_ONLY_NO_EXTERNAL_AUTHORIZATION",
        "reopen_policy": {"blocked_gate_submission": "REJECT_UNTIL_REOPEN", "reopen_requires_reason": True, "reopen_clears_blocker": True},
        "blocker_policy": {"blocked_count_visible": True, "reason_required": True, "max_reason_length": 240, "note": "A blocked gate cannot accept new evidence until an explicit reopen action with a reason is recorded."},
        "gates": gates,
        "package_ref": PENDING,
        "scope_ref": PENDING,
        "window_ref": PENDING,
        "rollback_ref": PENDING,
        "independent_verification_required": True,
    }


def template_sha256() -> str:
    return hashlib.sha256(json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "status": template()["status"], "template_sha256": template_sha256()}, indent=2))
