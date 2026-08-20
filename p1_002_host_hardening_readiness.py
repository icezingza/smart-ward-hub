from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "p1-002-host-hardening-readiness-v1"
PROJECT = "smart-ward-hub"
PENDING = "PENDING_EXTERNAL_APPOINTMENT"
OPAQUE_REF = re.compile(r"^(?:opaque|org|approval|evidence|artifact|scope|window|incident|rollback|commit|freeze|host):[A-Za-z0-9._-]+$")
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key)\s*[:=]\s*\S+)", re.IGNORECASE)
RAW_CONTACT = re.compile(r"(?:@|\+?\d[\d\s().-]{6,}|\b(?:mr|mrs|ms|นาย|นาง|นางสาว)\b)", re.IGNORECASE)

LOCKED_AUTHORIZATION = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}

CONTROLS = {
    "dedicated_service_identity": {
        "required_state": "non_admin_service_identity",
        "evidence_required": "windows_account_group_access_review",
        "external_required": True,
        "stop_conditions": ["service identity is administrator or access review is absent"],
    },
    "source_runtime_separation": {
        "required_state": "runtime_database_checkpoint_logs_outside_source_tree",
        "evidence_required": "path_acl_transcript",
        "external_required": True,
        "stop_conditions": ["runtime path resolves inside source tree or ACL is not restricted"],
    },
    "disk_encryption": {
        "required_state": "approved_encrypted_runtime_volume",
        "evidence_required": "windows_encryption_status_and_key_custody_record",
        "external_required": True,
        "stop_conditions": ["runtime volume encryption is absent or custody record is missing"],
    },
    "firewall_and_network": {
        "required_state": "explicit_allowlist_loopback_or_approved_gateway",
        "evidence_required": "firewall_export_and_approved_segment_port_scan",
        "external_required": True,
        "stop_conditions": ["wildcard exposure, unexpected listener or unapproved gateway path"],
    },
    "pilot_safe_api_defaults": {
        "required_state": "docs_disabled_no_auto_create_no_seed_data",
        "evidence_required": "deployment_readiness_transcript",
        "external_required": False,
        "stop_conditions": ["API docs, auto-create database or seed data enabled"],
    },
    "loopback_binding": {
        "required_state": "127.0.0.1_or_approved_gateway_only",
        "evidence_required": "process_and_listening_socket_transcript",
        "external_required": True,
        "stop_conditions": ["non-loopback bind without approved gateway and ACL"],
    },
    "identity_transport": {
        "required_state": "oidc_selected_static_only_for_bench",
        "evidence_required": "redacted_oidc_mtls_configuration_and_lifecycle_transcript",
        "external_required": True,
        "stop_conditions": ["static credentials used outside bench or real IdP/mTLS lifecycle is unverified"],
    },
    "time_integrity": {
        "required_state": "trusted_time_source_and_bounded_clock_skew",
        "evidence_required": "time_sync_and_clock_drift_record",
        "external_required": True,
        "stop_conditions": ["clock drift exceeds policy or time source is untrusted"],
    },
    "patch_state": {
        "required_state": "approved_os_runtime_dependency_inventory",
        "evidence_required": "host_patch_inventory_and_change_record",
        "external_required": True,
        "stop_conditions": ["unsupported runtime, missing security patch or unapproved change"],
    },
    "service_recovery": {
        "required_state": "operator_controlled_start_stop_restart_rollback",
        "evidence_required": "task_scheduler_or_supervisor_transcript_and_failure_drill",
        "external_required": True,
        "stop_conditions": ["rollback version is unknown or restart policy is not bounded"],
    },
    "backup_and_restore": {
        "required_state": "strict_manifest_isolated_restore_external_destination_pending",
        "evidence_required": "backup_restore_manifest_and_isolated_restore_transcript",
        "external_required": True,
        "stop_conditions": ["backup cannot be restored to isolated target or destination/retention is unapproved"],
    },
    "privacy_and_kiosk": {
        "required_state": "screen_ports_removable_media_and_kiosk_reviewed",
        "evidence_required": "site_privacy_and_human_factors_record",
        "external_required": True,
        "stop_conditions": ["kiosk escape, privacy exposure or unreviewed removable-media path"],
    },
    "monitoring": {
        "required_state": "health_disk_backup_auth_sync_and_alert_observables_defined",
        "evidence_required": "daily_preflight_and_alert_transcript",
        "external_required": True,
        "stop_conditions": ["health/backup/auth/sync alert has no owner or escalation rule"],
    },
}


class HostHardeningValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HostHardeningValidationError(message)


def _safe_ref(value: Any, field: str, *, allow_pending: bool = False) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    if allow_pending and value == PENDING:
        return value
    _require(OPAQUE_REF.fullmatch(value) is not None, f"{field} must be an opaque reference")
    _require(RAW_CONTACT.search(value) is None, f"{field} must not contain raw identity/contact data")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")
    return value


def _safe_text(value: Any, field: str) -> str:
    _require(isinstance(value, str) and value.strip(), f"{field} must be non-empty")
    _require(RAW_CONTACT.search(value) is None, f"{field} must not contain raw identity/contact data")
    _require(SECRET_MARKER.search(value) is None, f"{field} must not contain secret material")
    return value


def validate_host_hardening_manifest(payload: dict[str, Any], *, template_only: bool = False) -> dict[str, Any]:
    _require(isinstance(payload, dict), "manifest must be an object")
    allowed = {
        "schema_version", "project", "package_id", "source_revision", "freeze_manifest_sha256",
        "target", "status", "host_execution_status", "physical_validation", "clinical_validation",
        "software_evidence_only", "external_owner_appointment", "authorization_boundary", "controls",
        "common_controls", "independent_verification_required",
    }
    unknown = sorted(set(payload) - allowed)
    _require(not unknown, f"unknown fields: {unknown}")
    _require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version mismatch")
    _require(payload.get("project") == PROJECT, "project mismatch")
    if template_only:
        _require(payload.get("package_id") == PENDING, "template package_id must remain pending")
        _require(payload.get("source_revision") == PENDING, "template source_revision must remain pending")
        _require(payload.get("freeze_manifest_sha256") == "0" * 64, "template freeze hash must remain blank-safe")
    else:
        _safe_ref(payload.get("package_id"), "package_id")
        _safe_ref(payload.get("source_revision"), "source_revision")
        _require(isinstance(payload.get("freeze_manifest_sha256"), str) and re.fullmatch(r"[a-f0-9]{64}", payload["freeze_manifest_sha256"]) is not None, "freeze_manifest_sha256 must be lowercase SHA-256")

    _require(payload.get("target") == "Acer Spin N17H2 Fixed Hub candidate", "target mismatch")
    _require(payload.get("status") == "HOST_HARDENING_SOFTWARE_PREPARATION_READY", "status must remain software preparation ready")
    _require(payload.get("host_execution_status") == "NOT_STARTED", "host execution must remain NOT_STARTED")
    _require(payload.get("physical_validation") == "UNVERIFIED", "physical validation must remain UNVERIFIED")
    _require(payload.get("clinical_validation") == "PENDING", "clinical validation must remain PENDING")
    _require(payload.get("software_evidence_only") is True, "software_evidence_only must be true")
    _require(payload.get("external_owner_appointment") == PENDING, "external owner appointment must remain pending")
    _require(payload.get("authorization_boundary") == LOCKED_AUTHORIZATION, "authorization boundary must remain locked")
    _require(payload.get("independent_verification_required") is True, "independent_verification_required must be true")

    common = payload.get("common_controls")
    _require(isinstance(common, dict), "common_controls must be an object")
    _require(common.get("runtime_paths_outside_source_tree") is True, "runtime paths must be outside source tree")
    _require(common.get("api_docs_enabled") is False, "API docs must be disabled")
    _require(common.get("auto_create_db") is False, "auto-create DB must be disabled")
    _require(common.get("seed_data") is False, "seed data must be disabled")
    _require(common.get("loopback_only_reference") is True, "loopback-only reference must be true")
    _require(common.get("static_credentials_embedded") is False, "static credentials must not be embedded")
    _require(common.get("evidence_class") == "SOFTWARE_PREPARATION_ONLY", "evidence class mismatch")
    _safe_text(common.get("stop_rule"), "common_controls.stop_rule")
    for key in ("scope_ref", "window_ref", "rollback_ref"):
        if template_only:
            _require(common.get(key) == PENDING, f"template {key} must remain pending")
        else:
            _safe_ref(common.get(key), f"common_controls.{key}")

    controls = payload.get("controls")
    _require(isinstance(controls, dict) and set(controls) == set(CONTROLS), "controls must contain exactly the P1-002 control set")
    for name, contract in CONTROLS.items():
        control = controls[name]
        _require(isinstance(control, dict), f"controls.{name} must be an object")
        _require(control.get("required_state") == contract["required_state"], f"controls.{name}.required_state mismatch")
        _require(control.get("evidence_required") == contract["evidence_required"], f"controls.{name}.evidence_required mismatch")
        _require(control.get("external_required") is contract["external_required"], f"controls.{name}.external_required mismatch")
        _require(control.get("status") == ("SOFTWARE_PASS_EXTERNAL_PENDING" if contract["external_required"] else "SOFTWARE_PASS"), f"controls.{name}.status mismatch")
        _require(control.get("stop_conditions") == contract["stop_conditions"], f"controls.{name}.stop_conditions mismatch")
        for index, condition in enumerate(control["stop_conditions"]):
            _safe_text(condition, f"controls.{name}.stop_conditions[{index}]")
        if template_only:
            _require(control.get("evidence_ref") == PENDING, f"template controls.{name}.evidence_ref must remain pending")
        else:
            _safe_ref(control.get("evidence_ref"), f"controls.{name}.evidence_ref")

    return {
        "valid": True,
        "status": payload["status"],
        "host_execution_status": payload["host_execution_status"],
        "physical_validation": payload["physical_validation"],
        "external_owner_appointment": payload["external_owner_appointment"],
        "software_evidence_only": payload["software_evidence_only"],
    }


def template() -> dict[str, Any]:
    controls: dict[str, Any] = {}
    for name, contract in CONTROLS.items():
        controls[name] = {
            "required_state": contract["required_state"],
            "evidence_required": contract["evidence_required"],
            "external_required": contract["external_required"],
            "status": "SOFTWARE_PASS_EXTERNAL_PENDING" if contract["external_required"] else "SOFTWARE_PASS",
            "evidence_ref": PENDING,
            "stop_conditions": contract["stop_conditions"],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "package_id": PENDING,
        "source_revision": PENDING,
        "freeze_manifest_sha256": "0" * 64,
        "target": "Acer Spin N17H2 Fixed Hub candidate",
        "status": "HOST_HARDENING_SOFTWARE_PREPARATION_READY",
        "host_execution_status": "NOT_STARTED",
        "physical_validation": "UNVERIFIED",
        "clinical_validation": "PENDING",
        "software_evidence_only": True,
        "external_owner_appointment": PENDING,
        "authorization_boundary": dict(LOCKED_AUTHORIZATION),
        "common_controls": {
            "runtime_paths_outside_source_tree": True,
            "api_docs_enabled": False,
            "auto_create_db": False,
            "seed_data": False,
            "loopback_only_reference": True,
            "static_credentials_embedded": False,
            "evidence_class": "SOFTWARE_PREPARATION_ONLY",
            "scope_ref": PENDING,
            "window_ref": PENDING,
            "rollback_ref": PENDING,
            "stop_rule": "Stop deployment on source-tree runtime path, exposed docs, wildcard binding, embedded credential, unapproved volume, failed isolated restore or unknown rollback version.",
        },
        "controls": controls,
        "independent_verification_required": True,
    }


def template_sha256() -> str:
    encoded = json.dumps(template(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


if __name__ == "__main__":
    print(json.dumps({"schema_version": SCHEMA_VERSION, "status": template()["status"], "template_sha256": template_sha256()}, indent=2))
