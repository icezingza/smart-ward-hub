from __future__ import annotations

import json
from pathlib import Path

from p1_005_clinical_shadow_readiness import SCHEMA_VERSION, TRACKS, template, template_sha256

ROOT = Path(__file__).resolve().parent
EVIDENCE_DIR = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = EVIDENCE_DIR / "p1-005-clinical-shadow-readiness-template-20260820.json"
SCHEMA_PATH = EVIDENCE_DIR / "p1-005-clinical-shadow-readiness-schema-v1.json"


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(json.dumps(template(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schema/p1-005-clinical-shadow-readiness-v1",
        "title": "Smart Ward Hub P1-005 Clinical Shadow Readiness",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "project", "status", "shadow_execution", "clinical_governance", "clinical_validation", "real_world_authorization", "software_evidence_only", "external_owner_appointment", "authorization_boundary", "notification_mode", "evidence_class", "zero_pii_claim", "metrics_claim", "common_controls", "tracks", "independent_verification_required"],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "project": {"const": "smart-ward-hub"},
            "status": {"const": "SHADOW_MODE_SOFTWARE_PREPARATION_READY"},
            "shadow_execution": {"const": "NOT_STARTED"},
            "clinical_governance": {"const": "PENDING"},
            "clinical_validation": {"const": "PENDING"},
            "real_world_authorization": {"const": False},
            "software_evidence_only": {"const": True},
            "external_owner_appointment": {"type": "string"},
            "authorization_boundary": {"const": {"external_authority": "NONE", "clinical_validation_authorized": False, "production_authorized": False, "runtime_authority": "NONE", "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"}},
            "notification_mode": {"const": "DISABLED"},
            "evidence_class": {"const": "SOFTWARE_SHADOW_MODE_NOT_CLINICAL_ACCURACY"},
            "zero_pii_claim": {"const": "TESTED_INPUT_MARKER_BOUNDARY_NOT_SYSTEMWIDE_PRIVACY_PROOF"},
            "metrics_claim": {"const": "NON_ACCURACY_WORKFLOW_DATA_QUALITY_ONLY"},
            "common_controls": {"type": "object", "additionalProperties": False, "required": ["max_context_length", "approved_signal_types", "review_classifications", "review_coverage_required", "denominator_explicit", "accuracy_claim_forbidden", "manual_fallback", "retention_decision", "protocol_ref", "scope_ref", "window_ref", "rollback_ref", "training_ref", "review_plan_ref", "stop_rule"]},
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
