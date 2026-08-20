from __future__ import annotations

import json
from pathlib import Path

from p1_002_host_hardening_readiness import CONTROLS, SCHEMA_VERSION, template, template_sha256

ROOT = Path(__file__).resolve().parent
EVIDENCE_DIR = ROOT / "evals/micro_rag/evidence"
TEMPLATE_PATH = EVIDENCE_DIR / "p1-002-host-hardening-readiness-template-20260820.json"
SCHEMA_PATH = EVIDENCE_DIR / "p1-002-host-hardening-readiness-schema-v1.json"


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(json.dumps(template(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smart-ward-hub.invalid/schema/p1-002-host-hardening-readiness-v1",
        "title": "Smart Ward Hub P1-002 Host Hardening Readiness",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version", "project", "package_id", "source_revision", "freeze_manifest_sha256", "target",
            "status", "host_execution_status", "physical_validation", "clinical_validation", "software_evidence_only",
            "external_owner_appointment", "authorization_boundary", "controls", "common_controls", "independent_verification_required",
        ],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "project": {"const": "smart-ward-hub"},
            "package_id": {"type": "string"},
            "source_revision": {"type": "string"},
            "freeze_manifest_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "target": {"const": "Acer Spin N17H2 Fixed Hub candidate"},
            "status": {"const": "HOST_HARDENING_SOFTWARE_PREPARATION_READY"},
            "host_execution_status": {"const": "NOT_STARTED"},
            "physical_validation": {"const": "UNVERIFIED"},
            "clinical_validation": {"const": "PENDING"},
            "software_evidence_only": {"const": True},
            "external_owner_appointment": {"type": "string"},
            "authorization_boundary": {"const": {"external_authority": "NONE", "clinical_validation_authorized": False, "production_authorized": False, "runtime_authority": "NONE", "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"}},
            "controls": {"type": "object", "additionalProperties": False, "required": list(CONTROLS), "description": "Exact P1-002 host hardening control set; external controls remain pending target-host evidence."},
            "common_controls": {"type": "object", "additionalProperties": False, "required": ["runtime_paths_outside_source_tree", "api_docs_enabled", "auto_create_db", "seed_data", "loopback_only_reference", "static_credentials_embedded", "evidence_class", "scope_ref", "window_ref", "rollback_ref", "stop_rule"]},
            "independent_verification_required": {"const": True},
        },
    }
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TEMPLATE={TEMPLATE_PATH}")
    print(f"SCHEMA={SCHEMA_PATH}")
    print(f"TEMPLATE_SHA256={template_sha256()}")


if __name__ == "__main__":
    main()
