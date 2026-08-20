from __future__ import annotations

import json
from pathlib import Path

from p1_007_external_validation_readiness import GATE_DEFINITIONS, SCHEMA_VERSION, template, template_sha256

ROOT = Path(__file__).resolve().parent
EVIDENCE_DIR = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = EVIDENCE_DIR / "p1-007-external-validation-readiness-template-20260820.json"
SCHEMA_PATH = EVIDENCE_DIR / "p1-007-external-validation-readiness-schema-v1.json"


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(json.dumps(template(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schema/p1-007-external-validation-readiness-v1",
        "title": "Smart Ward Hub P1-007 External Validation Readiness",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "project", "status", "gate_count", "gate_status_counts", "external_execution_status", "external_owner_appointment", "real_world_authorization", "clinical_validation_authorized", "production_authorized", "runtime_authority", "pilot_gate_status", "authorization_boundary", "coordination_evidence_only", "evidence_class", "claim_boundary", "reopen_policy", "blocker_policy", "gates", "package_ref", "scope_ref", "window_ref", "rollback_ref", "independent_verification_required"],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "project": {"const": "smart-ward-hub"},
            "status": {"const": "COORDINATION_SOFTWARE_READY"},
            "gate_count": {"const": 10},
            "gate_status_counts": {"const": {"OPEN": 10, "EVIDENCE_SUBMITTED": 0, "BLOCKED": 0}},
            "external_execution_status": {"const": "NOT_STARTED"},
            "external_owner_appointment": {"type": "string"},
            "real_world_authorization": {"const": False},
            "clinical_validation_authorized": {"const": False},
            "production_authorized": {"const": False},
            "runtime_authority": {"const": "NONE"},
            "pilot_gate_status": {"const": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"},
            "authorization_boundary": {"const": {"external_authority": "NONE", "clinical_validation_authorized": False, "production_authorized": False, "runtime_authority": "NONE", "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"}},
            "coordination_evidence_only": {"const": True},
            "evidence_class": {"const": "COORDINATION_ARTIFACT_UNVERIFIED"},
            "claim_boundary": {"const": "CONTROLLED_PROTOTYPE_SOFTWARE_EVIDENCE_ONLY_NO_EXTERNAL_AUTHORIZATION"},
            "reopen_policy": {"type": "object", "additionalProperties": False, "required": ["blocked_gate_submission", "reopen_requires_reason", "reopen_clears_blocker"]},
            "blocker_policy": {"type": "object", "additionalProperties": False, "required": ["blocked_count_visible", "reason_required", "max_reason_length", "note"]},
            "gates": {"type": "object", "additionalProperties": False, "required": list(GATE_DEFINITIONS)},
            "package_ref": {"type": "string"},
            "scope_ref": {"type": "string"},
            "window_ref": {"type": "string"},
            "rollback_ref": {"type": "string"},
            "independent_verification_required": {"const": True},
        },
    }
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TEMPLATE={TEMPLATE_PATH}")
    print(f"SCHEMA={SCHEMA_PATH}")
    print(f"TEMPLATE_SHA256={template_sha256()}")


if __name__ == "__main__":
    main()
