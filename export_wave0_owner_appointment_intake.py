from __future__ import annotations

import json
from pathlib import Path

from wave0_owner_appointment_intake import SCHEMA_VERSION, REQUIRED_ROLES, template, template_sha256

ROOT = Path(__file__).resolve().parent
EVIDENCE_DIR = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = EVIDENCE_DIR / "wave0-owner-appointment-intake-template-20260820.json"
SCHEMA_PATH = EVIDENCE_DIR / "wave0-owner-appointment-intake-schema-v1.json"


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(json.dumps(template(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schema/wave0-owner-appointment-intake-v1",
        "title": "Smart Ward Hub Wave 0 Owner Appointment Intake",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "package_id", "project", "repository", "source_revision", "freeze_manifest_sha256", "scope", "test_window", "roles", "stop_authority", "rollback_plan", "evidence_intake", "authorization_boundary", "status", "external_execution_authorized", "production_authorized", "clinical_validation_authorized", "independent_verification_required"],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "package_id": {"type": "string"},
            "project": {"const": "smart-ward-hub"},
            "repository": {"const": "icezingza/smart-ward-hub"},
            "source_revision": {"type": "string"},
            "freeze_manifest_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "status": {"enum": ["OWNER_APPOINTMENT_TEMPLATE", "OWNER_APPOINTMENT_SUBMITTED", "BLOCKED"]},
            "external_execution_authorized": {"const": False},
            "production_authorized": {"const": False},
            "clinical_validation_authorized": {"const": False},
            "independent_verification_required": {"const": True},
            "roles": {"type": "object", "additionalProperties": False, "required": list(REQUIRED_ROLES), "description": "Each role must resolve to a distinct opaque actor/organization/appointment reference before submission."},
            "scope": {"type": "object", "additionalProperties": False, "required": ["scope_id", "signed_scope_ref", "approved_by_ref", "in_scope", "out_of_scope"]},
            "test_window": {"type": "object", "additionalProperties": False, "required": ["start_utc", "end_utc", "approval_ref", "allowlist_ref"]},
            "stop_authority": {"type": "object", "additionalProperties": False, "required": ["stop_rule_ref", "notification_ref"]},
            "rollback_plan": {"type": "object", "additionalProperties": False, "required": ["target_revision", "owner_approval_ref", "restore_drill_ref"]},
            "evidence_intake": {"type": "object", "additionalProperties": False, "required": ["submission_manifest_ref", "custody_ref", "redaction"]},
            "authorization_boundary": {"const": {"external_authority": "NONE", "clinical_validation_authorized": False, "production_authorized": False, "runtime_authority": "NONE", "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"}},
        },
    }
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TEMPLATE={TEMPLATE_PATH}")
    print(f"SCHEMA={SCHEMA_PATH}")
    print(f"TEMPLATE_SHA256={template_sha256()}")


if __name__ == "__main__":
    main()
