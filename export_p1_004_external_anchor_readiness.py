from __future__ import annotations

import json
from pathlib import Path

from p1_004_external_anchor_readiness import SCHEMA_VERSION, TRACKS, template, template_sha256

ROOT = Path(__file__).resolve().parent
EVIDENCE_DIR = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = EVIDENCE_DIR / "p1-004-external-anchor-readiness-template-20260820.json"
SCHEMA_PATH = EVIDENCE_DIR / "p1-004-external-anchor-readiness-schema-v1.json"


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(json.dumps(template(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schema/p1-004-external-anchor-readiness-v1",
        "title": "Smart Ward Hub P1-004 External Anchor Readiness",
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "project", "package_id", "source_revision", "freeze_manifest_sha256", "status", "anchor_execution", "independent_provider_validation", "clinical_validation", "software_evidence_only", "external_owner_appointment", "authorization_boundary", "software_provider_identity", "local_anchor_claim", "external_worm_verified", "tracks", "common_controls", "independent_verification_required"],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "project": {"const": "smart-ward-hub"},
            "package_id": {"type": "string"},
            "source_revision": {"type": "string"},
            "freeze_manifest_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "status": {"const": "EXTERNAL_ANCHOR_SOFTWARE_PREPARATION_READY"},
            "anchor_execution": {"const": "NOT_STARTED"},
            "independent_provider_validation": {"const": "UNVERIFIED"},
            "clinical_validation": {"const": "PENDING"},
            "software_evidence_only": {"const": True},
            "external_owner_appointment": {"type": "string"},
            "authorization_boundary": {"const": {"external_authority": "NONE", "clinical_validation_authorized": False, "production_authorized": False, "runtime_authority": "NONE", "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"}},
            "software_provider_identity": {"const": "software-anchor-stub"},
            "local_anchor_claim": {"const": "TAMPER_EVIDENT_WITHIN_EDGE_TRUST_BOUNDARY"},
            "external_worm_verified": {"const": False},
            "tracks": {"type": "object", "additionalProperties": False, "required": list(TRACKS)},
            "common_controls": {"type": "object", "additionalProperties": False, "required": ["evidence_class", "idempotency_formula", "receipt_verification_required", "delete_refusal_required", "trusted_time", "retention_and_access", "scope_ref", "window_ref", "rollback_ref", "provider_ref", "stop_rule"]},
            "independent_verification_required": {"const": True},
        },
    }
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TEMPLATE={TEMPLATE_PATH}")
    print(f"SCHEMA={SCHEMA_PATH}")
    print(f"TEMPLATE_SHA256={template_sha256()}")


if __name__ == "__main__":
    main()
