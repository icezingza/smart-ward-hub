from __future__ import annotations

import json
from pathlib import Path

from wave1_software_preparation import SCHEMA_VERSION, TRACKS, template, template_sha256

ROOT = Path(__file__).resolve().parent
EVIDENCE_DIR = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = EVIDENCE_DIR / "wave1-software-preparation-template-20260820.json"
SCHEMA_PATH = EVIDENCE_DIR / "wave1-software-preparation-schema-v1.json"


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(json.dumps(template(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schema/wave1-software-preparation-v1",
        "title": "Smart Ward Hub Wave 1 Software Preparation",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "project", "package_id", "source_revision", "freeze_manifest_sha256",
            "status", "environment", "execution_status", "external_execution_authorized",
            "authorization_boundary", "tracks", "common_controls", "independent_verification_required",
        ],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "project": {"const": "smart-ward-hub"},
            "package_id": {"type": "string"},
            "source_revision": {"type": "string"},
            "freeze_manifest_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "status": {"const": "SOFTWARE_PREPARATION_READY"},
            "environment": {"const": "ISOLATED_NON_PRODUCTION_ONLY"},
            "execution_status": {"const": "NOT_STARTED"},
            "external_execution_authorized": {"const": False},
            "independent_verification_required": {"const": True},
            "authorization_boundary": {"const": {"external_authority": "NONE", "clinical_validation_authorized": False, "production_authorized": False, "runtime_authority": "NONE", "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"}},
            "tracks": {
                "type": "object",
                "additionalProperties": False,
                "required": list(TRACKS),
                "description": "Exactly GV-04 OIDC/mTLS, GV-08 key custody and GV-06 Acer bench tracks; all remain NOT_STARTED and UNVERIFIED externally.",
            },
            "common_controls": {
                "type": "object",
                "additionalProperties": False,
                "required": ["synthetic_data_only", "raw_patient_data_allowed", "production_credentials_allowed", "private_key_material_allowed", "raw_serial_frames_allowed", "evidence_class", "scope_ref", "window_ref", "rollback_ref", "stop_rule"],
            },
        },
    }
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TEMPLATE={TEMPLATE_PATH}")
    print(f"SCHEMA={SCHEMA_PATH}")
    print(f"TEMPLATE_SHA256={template_sha256()}")


if __name__ == "__main__":
    main()
