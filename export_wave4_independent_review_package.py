from __future__ import annotations

import json
from pathlib import Path

from wave4_independent_review_package import ARTIFACT_PATHS, SCHEMA_VERSION, TEST_SPECS, build_local_package, template, template_sha256

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = OUT / "wave4-independent-review-package-template-20260821.json"
LOCAL_PATH = OUT / "wave4-independent-review-package-local-index-20260821.json"
SCHEMA_PATH = OUT / "wave4-independent-review-package-schema-v1.json"


def schema() -> dict:
    mapping_entry = {
        "type": "object",
        "additionalProperties": False,
        "required": ["test_case_id", "focus", "evidence_class", "local_artifact_refs", "external_verification_status", "reviewer_action"],
        "properties": {
            "test_case_id": {"type": "string", "pattern": "^T-(0[1-9]|1[0-2])$"},
            "focus": {"type": "string"},
            "evidence_class": {"type": "string"},
            "local_artifact_refs": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "external_verification_status": {"const": "PENDING_EXTERNAL"},
            "reviewer_action": {"type": "string"},
        },
    }
    artifact_entry = {
        "type": "object",
        "additionalProperties": False,
        "required": ["artifact_ref", "repo_path", "artifact_type", "artifact_sha256", "source_revision", "evidence_class", "prepared_by_role", "redaction", "raw_identity_present", "external_verification_status"],
        "properties": {
            "artifact_ref": {"type": "string"},
            "repo_path": {"type": "string"},
            "artifact_type": {"type": "string"},
            "artifact_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "source_revision": {"type": "string"},
            "evidence_class": {"const": "SOFTWARE_REPOSITORY"},
            "prepared_by_role": {"const": "evidence_custodian"},
            "redaction": {"const": "PASS"},
            "raw_identity_present": {"const": False},
            "external_verification_status": {"const": "PENDING_EXTERNAL"},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schemas/wave4-independent-review-package-v1",
        "title": "Smart Ward Hub Wave 4 Independent Review Package",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "project", "package_id", "source_revision", "freeze_manifest_sha256", "package_state", "evidence_class", "wave_e_bundle_state", "independent_review_status", "external_owner_appointment", "mapping", "artifacts", "review_contract", "authorization_boundary", "independent_verification_required", "redaction", "raw_identity_present"],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "project": {"const": "smart-ward-hub"},
            "package_id": {"type": "string"},
            "source_revision": {"type": "string"},
            "freeze_manifest_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "package_state": {"const": "READY_FOR_EXTERNAL_OWNER_APPOINTMENT"},
            "evidence_class": {"const": "SOFTWARE_COORDINATION_ONLY"},
            "wave_e_bundle_state": {"const": "NOT_EXECUTED"},
            "independent_review_status": {"const": "NOT_STARTED"},
            "external_owner_appointment": {"const": "PENDING_EXTERNAL_APPOINTMENT"},
            "mapping": {"type": "array", "minItems": 12, "maxItems": 12, "items": mapping_entry},
            "artifacts": {"type": "array", "minItems": len(ARTIFACT_PATHS), "maxItems": len(ARTIFACT_PATHS), "items": artifact_entry},
            "review_contract": {"const": "wave-e-evidence-bundle-v1"},
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
            "independent_verification_required": {"const": True},
            "redaction": {"const": "PASS"},
            "raw_identity_present": {"const": False},
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(json.dumps(template(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    local = build_local_package(ROOT)
    LOCAL_PATH.write_text(json.dumps(local, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    SCHEMA_PATH.write_text(json.dumps(schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"TEMPLATE={TEMPLATE_PATH}")
    print(f"LOCAL_INDEX={LOCAL_PATH}")
    print(f"SCHEMA={SCHEMA_PATH}")
    print(f"TEMPLATE_SHA256={template_sha256()}")
    print(f"MAPPING_COUNT={len(local['mapping'])}")
    print(f"ARTIFACT_COUNT={len(local['artifacts'])}")


if __name__ == "__main__":
    main()
