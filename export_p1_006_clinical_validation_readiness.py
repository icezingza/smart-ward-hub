from __future__ import annotations

import json
from pathlib import Path

from p1_006_clinical_validation_readiness import SCHEMA_VERSION, TRACKS, template, template_sha256

ROOT = Path(__file__).resolve().parent
EVIDENCE_DIR = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = EVIDENCE_DIR / "p1-006-clinical-validation-readiness-template-20260820.json"
SCHEMA_PATH = EVIDENCE_DIR / "p1-006-clinical-validation-readiness-schema-v1.json"


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(json.dumps(template(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schema/p1-006-clinical-validation-readiness-v1",
        "title": "Smart Ward Hub P1-006 Clinical Validation Readiness",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "project", "status", "preflight_status", "execution_status", "clinical_governance", "clinical_validation", "real_world_authorization", "software_evidence_only", "external_owner_appointment", "authorization_boundary", "evidence_class", "clinical_claim_boundary", "clinical_shadow_dependency", "protocol_ref", "scope_ref", "window_ref", "rollback_ref", "consent_ref", "retention_ref", "training_ref", "analysis_ref", "analysis_semantics", "hard_stops", "tracks", "independent_verification_required"],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "project": {"const": "smart-ward-hub"},
            "status": {"const": "CLINICAL_VALIDATION_SOFTWARE_PREFLIGHT_READY"},
            "preflight_status": {"const": "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW"},
            "execution_status": {"const": "NOT_STARTED"},
            "clinical_governance": {"const": "PENDING"},
            "clinical_validation": {"const": "PENDING"},
            "real_world_authorization": {"const": False},
            "software_evidence_only": {"const": True},
            "external_owner_appointment": {"type": "string"},
            "authorization_boundary": {"const": {"external_authority": "NONE", "clinical_validation_authorized": False, "production_authorized": False, "runtime_authority": "NONE", "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"}},
            "evidence_class": {"const": "SOFTWARE_PREFLIGHT_UNVERIFIED"},
            "clinical_claim_boundary": {"const": "NO_CLINICAL_VALIDATION_OR_ACCURACY_CLAIM"},
            "clinical_shadow_dependency": {"const": "P1_005_SOFTWARE_SHADOW_CONTRACT_EXTERNAL_APPROVAL_PENDING"},
            "protocol_ref": {"type": "string"},
            "scope_ref": {"type": "string"},
            "window_ref": {"type": "string"},
            "rollback_ref": {"type": "string"},
            "consent_ref": {"type": "string"},
            "retention_ref": {"type": "string"},
            "training_ref": {"type": "string"},
            "analysis_ref": {"type": "string"},
            "analysis_semantics": {"type": "object", "additionalProperties": False, "required": ["accuracy_claim_forbidden", "clinical_effectiveness_claim_forbidden", "review_coverage_required", "denominator_explicit", "unreviewed_events_visible", "synthetic_data_not_clinical_evidence", "note"]},
            "hard_stops": {"type": "array", "minItems": 10, "maxItems": 10, "items": {"type": "string"}},
            "tracks": {"type": "object", "additionalProperties": False, "required": list(TRACKS)},
            "independent_verification_required": {"const": True},
        },
    }
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TEMPLATE={TEMPLATE_PATH}")
    print(f"SCHEMA={SCHEMA_PATH}")
    print(f"TEMPLATE_SHA256={template_sha256()}")


if __name__ == "__main__":
    main()
