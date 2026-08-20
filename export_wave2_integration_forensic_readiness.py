from __future__ import annotations

import json
from pathlib import Path

from wave2_integration_forensic_readiness import SCHEMA_VERSION, template, template_sha256

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = OUT / "wave2-integration-forensic-readiness-template-20260821.json"
SCHEMA_PATH = OUT / "wave2-integration-forensic-readiness-schema-v1.json"


def schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schemas/wave2-integration-forensic-readiness-v1",
        "title": "Smart Ward Hub Wave 2 Integration and Forensic Readiness",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "project", "source_revision", "freeze_manifest_sha256", "status",
            "execution_status", "external_integration", "clinical_validation", "software_evidence_only",
            "external_owner_appointment", "authorization_boundary", "tracks", "common_controls",
            "required_external_prerequisites", "independent_verification_required",
        ],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "project": {"const": "smart-ward-hub"},
            "source_revision": {"type": "string"},
            "freeze_manifest_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "status": {"const": "WAVE2_SOFTWARE_PREPARATION_READY"},
            "execution_status": {"const": "NOT_STARTED"},
            "external_integration": {"const": "UNVERIFIED"},
            "clinical_validation": {"const": "PENDING"},
            "software_evidence_only": {"const": True},
            "external_owner_appointment": {"const": "PENDING_EXTERNAL_APPOINTMENT"},
            "authorization_boundary": {
                "type": "object",
                "additionalProperties": False,
                "required": ["external_authority", "clinical_validation_authorized", "production_authorized", "runtime_authority", "pilot_gate_status"],
                "properties": {
                    "external_authority": {"const": "NONE"},
                    "clinical_validation_authorized": {"const": False},
                    "production_authorized": {"const": False},
                    "runtime_authority": {"const": "NONE"},
                    "pilot_gate_status": {"const": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"},
                },
            },
            "tracks": {
                "type": "object",
                "additionalProperties": False,
                "required": ["GV-03", "GV-07"],
                "properties": {},
            },
            "common_controls": {"type": "object", "additionalProperties": False},
            "required_external_prerequisites": {"type": "array", "minItems": 8, "maxItems": 8, "uniqueItems": True},
            "independent_verification_required": {"const": True},
        },
    }


def _schema() -> dict:
    value = schema()
    value["properties"]["tracks"]["properties"] = {
        "GV-03": {
            "type": "object",
            "additionalProperties": False,
            "required": ["gate", "title", "software_state", "external_required", "evidence_refs", "stop_conditions"],
        },
        "GV-07": {
            "type": "object",
            "additionalProperties": False,
            "required": ["gate", "title", "software_state", "external_required", "evidence_refs", "stop_conditions"],
        },
    }
    return value


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    template_payload = template()
    TEMPLATE_PATH.write_text(json.dumps(template_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    SCHEMA_PATH.write_text(json.dumps(_schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"TEMPLATE={TEMPLATE_PATH}")
    print(f"SCHEMA={SCHEMA_PATH}")
    print(f"TEMPLATE_SHA256={template_sha256()}")


if __name__ == "__main__":
    main()
