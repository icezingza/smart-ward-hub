from __future__ import annotations

import json
from pathlib import Path

from independent_reviewer_readiness_preflight import CHECKS, EXTERNAL_INPUTS, SCHEMA_VERSION, template, template_sha256, build_preflight
from wave4_independent_review_package import TOP_LEVEL_FREEZE_REFERENCE

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = OUT / "independent-reviewer-readiness-preflight-template-20260821.json"
LOCAL_PATH = OUT / "independent-reviewer-readiness-preflight-local-20260821.json"
SCHEMA_PATH = OUT / "independent-reviewer-readiness-preflight-schema-v1.json"


def schema() -> dict:
    checklist = {
        "type": "object",
        "additionalProperties": False,
        "required": ["check_id", "title", "owner_role", "required_status", "status", "external_action"],
        "properties": {
            "check_id": {"type": "string", "pattern": "^IRP-(0[1-9]|1[0-2])$"},
            "title": {"type": "string"},
            "owner_role": {"type": "string"},
            "required_status": {"type": "string"},
            "status": {"type": "string"},
            "external_action": {"type": "string"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schemas/independent-reviewer-readiness-preflight-v1",
        "title": "Smart Ward Hub Independent Reviewer Readiness Preflight",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "project", "preflight_id", "source_revision", "freeze_manifest_sha256", "local_index_sha256", "status", "submission_status", "reviewer_appointment", "external_decision", "package_state", "wave_e_bundle_state", "independent_review_status", "mapping_count", "artifact_count", "reviewer_checklist", "external_inputs_pending", "authorization_boundary", "software_evidence_only", "independent_verification_required", "redaction", "raw_identity_present"],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "project": {"const": "smart-ward-hub"},
            "preflight_id": {"type": "string"},
            "source_revision": {"type": "string"},
            "freeze_manifest_sha256": {"const": TOP_LEVEL_FREEZE_REFERENCE},
            "local_index_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "status": {"const": "REVIEWER_PRECHECK_READY_FOR_EXTERNAL_APPOINTMENT"},
            "submission_status": {"const": "NOT_SUBMITTED"},
            "reviewer_appointment": {"const": "PENDING_EXTERNAL_APPOINTMENT"},
            "external_decision": {"const": "NOT_ISSUED"},
            "package_state": {"const": "READY_FOR_EXTERNAL_OWNER_APPOINTMENT"},
            "wave_e_bundle_state": {"const": "NOT_EXECUTED"},
            "independent_review_status": {"const": "NOT_STARTED"},
            "mapping_count": {"const": 12},
            "artifact_count": {"const": 22},
            "reviewer_checklist": {"type": "array", "minItems": len(CHECKS), "maxItems": len(CHECKS), "items": checklist},
            "external_inputs_pending": {"type": "array", "minItems": len(EXTERNAL_INPUTS), "maxItems": len(EXTERNAL_INPUTS), "uniqueItems": True, "items": {"type": "string"}},
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
            "software_evidence_only": {"const": True},
            "independent_verification_required": {"const": True},
            "redaction": {"const": "PASS"},
            "raw_identity_present": {"const": False},
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(json.dumps(template(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOCAL_PATH.write_text(json.dumps(build_preflight(ROOT), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    SCHEMA_PATH.write_text(json.dumps(schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"TEMPLATE={TEMPLATE_PATH}")
    print(f"LOCAL_PREFLIGHT={LOCAL_PATH}")
    print(f"SCHEMA={SCHEMA_PATH}")
    print(f"TEMPLATE_SHA256={template_sha256()}")
    print(f"CHECKLIST_COUNT={len(CHECKS)}")
    print(f"EXTERNAL_INPUT_COUNT={len(EXTERNAL_INPUTS)}")


if __name__ == "__main__":
    main()
