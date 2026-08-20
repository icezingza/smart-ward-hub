from __future__ import annotations

import json
from pathlib import Path

from wave3_governance_host_clinical_readiness import SCHEMA_VERSION, TRACKS, template, template_sha256

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = OUT / "wave3-governance-host-clinical-readiness-template-20260821.json"
SCHEMA_PATH = OUT / "wave3-governance-host-clinical-readiness-schema-v1.json"


def _track_schema() -> dict:
    properties: dict[str, object] = {}
    for gate in TRACKS:
        properties[gate] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["gate", "title", "software_state", "external_required", "evidence_refs", "stop_conditions"],
            "properties": {
                "gate": {"const": gate},
                "title": {"type": "string"},
                "software_state": {"type": "string"},
                "external_required": {"const": True},
                "evidence_refs": {"type": "object", "additionalProperties": {"type": "string"}},
                "stop_conditions": {"type": "array", "minItems": 3, "items": {"type": "string"}},
            },
        }
    return {"type": "object", "additionalProperties": False, "required": list(TRACKS), "properties": properties}


def schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schemas/wave3-governance-host-clinical-readiness-v1",
        "title": "Smart Ward Hub Wave 3 Governance Host Clinical Readiness",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "project", "source_revision", "freeze_manifest_sha256", "status", "execution_status", "clinical_governance", "host_validation", "privacy_review", "clinical_operations", "clinical_validation", "software_evidence_only", "external_owner_appointment", "authorization_boundary", "tracks", "common_controls", "required_external_prerequisites", "independent_verification_required"],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "project": {"const": "smart-ward-hub"},
            "source_revision": {"type": "string"},
            "freeze_manifest_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "status": {"const": "WAVE3_SOFTWARE_PREPARATION_READY"},
            "execution_status": {"const": "NOT_STARTED"},
            "clinical_governance": {"const": "PENDING"},
            "host_validation": {"const": "UNVERIFIED"},
            "privacy_review": {"const": "UNVERIFIED"},
            "clinical_operations": {"const": "NOT_STARTED"},
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
            "tracks": _track_schema(),
            "common_controls": {"type": "object", "additionalProperties": False},
            "required_external_prerequisites": {"type": "array", "minItems": 16, "maxItems": 16, "uniqueItems": True, "items": {"type": "string"}},
            "independent_verification_required": {"const": True},
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(json.dumps(template(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    SCHEMA_PATH.write_text(json.dumps(schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"TEMPLATE={TEMPLATE_PATH}")
    print(f"SCHEMA={SCHEMA_PATH}")
    print(f"TEMPLATE_SHA256={template_sha256()}")


if __name__ == "__main__":
    main()
