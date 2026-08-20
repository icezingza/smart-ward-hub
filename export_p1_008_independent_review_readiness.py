from __future__ import annotations

import json
from pathlib import Path

from p1_008_independent_review_readiness import SCHEMA_VERSION, TRACK_DEFINITIONS, template, template_sha256


ROOT = Path(__file__).resolve().parent
EVIDENCE_DIR = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = EVIDENCE_DIR / "p1-008-independent-review-readiness-template-20260821.json"
SCHEMA_PATH = EVIDENCE_DIR / "p1-008-independent-review-readiness-schema-v1.json"


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(json.dumps(template(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schema/p1-008-independent-review-readiness-v1",
        "title": "Smart Ward Hub P1-008 Independent Review Readiness",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "project", "status", "track_count", "software_track_status_counts",
            "external_review_status_counts", "review_session_status", "external_review_status",
            "external_owner_appointment", "real_world_authorization", "clinical_validation_authorized",
            "production_authorized", "runtime_authority", "pilot_gate_status", "authorization_boundary",
            "software_evidence_only", "independent_verification_required", "evidence_class", "claim_boundary",
            "tracks", "review_session_ref", "dossier_ref", "findings_export_ref", "external_decision_ref",
            "rollback_ref", "stop_rule",
        ],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "project": {"const": "smart-ward-hub"},
            "status": {"const": "SOFTWARE_REVIEW_READY"},
            "track_count": {"const": 7},
            "software_track_status_counts": {"const": {"SOFTWARE_VERIFIED": 7}},
            "external_review_status_counts": {"const": {"PENDING_EXTERNAL_REVIEW": 7}},
            "review_session_status": {"const": "SOFTWARE_DRY_RUN_VERIFIED"},
            "external_review_status": {"const": "PENDING_EXTERNAL_REVIEW"},
            "external_owner_appointment": {"type": "string"},
            "real_world_authorization": {"const": False},
            "clinical_validation_authorized": {"const": False},
            "production_authorized": {"const": False},
            "runtime_authority": {"const": "NONE"},
            "pilot_gate_status": {"const": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"},
            "authorization_boundary": {"const": {
                "external_authority": "NONE",
                "clinical_validation_authorized": False,
                "production_authorized": False,
                "runtime_authority": "NONE",
                "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
            }},
            "software_evidence_only": {"const": True},
            "independent_verification_required": {"const": True},
            "evidence_class": {"const": "SOFTWARE_VERIFIED_EXTERNAL_REVIEW_PENDING"},
            "claim_boundary": {"const": "CONTROLLED_PRODUCTION_PROTOTYPE_SOFTWARE_VERIFICATION_ONLY_CLINICAL_VALIDATION_PENDING"},
            "tracks": {
                "type": "object",
                "additionalProperties": False,
                "required": list(TRACK_DEFINITIONS),
                "properties": {
                    track_id: {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["domain", "software_status", "external_status", "software_evidence_refs", "external_evidence_refs", "stop_condition"],
                    }
                    for track_id in TRACK_DEFINITIONS
                },
            },
            "review_session_ref": {"type": "string"},
            "dossier_ref": {"type": "string"},
            "findings_export_ref": {"type": "string"},
            "external_decision_ref": {"type": "string"},
            "rollback_ref": {"type": "string"},
            "stop_rule": {"type": "string"},
        },
    }
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TEMPLATE={TEMPLATE_PATH}")
    print(f"SCHEMA={SCHEMA_PATH}")
    print(f"TEMPLATE_SHA256={template_sha256()}")


if __name__ == "__main__":
    main()
