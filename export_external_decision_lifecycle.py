from __future__ import annotations

import argparse
import json
from pathlib import Path

from external_decision_lifecycle import (
    AUTHORIZATION_BOUNDARY,
    BLOCKED_SIMULATION,
    DECISION_EXPIRED,
    DECISION_REVOKED,
    LIFECYCLE_SCHEMA_VERSION,
    PENDING_EXTERNAL_VERIFICATION,
    RECEIVED_FOR_SIMULATION,
    REOPENED_WITH_REASON,
    REQUIRES_CLARIFICATION,
    RESUBMISSION_REQUIRED,
    TRANSITIONS,
)
from external_decision_record import canonical_sha256, template, validate


def export(output: Path) -> dict:
    record_template = template()
    validation = validate(record_template, template_only=True)
    snapshot = {
        "schema_version": LIFECYCLE_SCHEMA_VERSION,
        "project": record_template["project"],
        "repository": record_template["repository"],
        "snapshot_kind": "EXTERNAL_DECISION_LIFECYCLE_TEMPLATE",
        "lifecycle_state": "LIFECYCLE_TEMPLATE_PENDING_EXTERNAL_RECORD",
        "lifecycle_instantiated": False,
        "record_template_status": record_template["status"],
        "record_template_evidence_class": record_template["evidence_class"],
        "record_template_validation": validation,
        "record_template_sha256": canonical_sha256(record_template),
        "state_registry": {
            state: sorted(targets)
            for state, targets in sorted(TRANSITIONS.items())
        },
        "initial_state_for_nonexpired_received_record": PENDING_EXTERNAL_VERIFICATION,
        "expired_state": DECISION_EXPIRED,
        "revoked_state": DECISION_REVOKED,
        "simulation_states": [
            BLOCKED_SIMULATION,
            REOPENED_WITH_REASON,
            RECEIVED_FOR_SIMULATION,
            RESUBMISSION_REQUIRED,
            REQUIRES_CLARIFICATION,
        ],
        "external_decision_verified": False,
        "authorization_promoted": False,
        "external_execution_authorized": False,
        "production_authorized": False,
        "clinical_validation_authorized": False,
        "authorization_boundary": AUTHORIZATION_BOUNDARY,
        "software_simulation_only": True,
        "external_authority": "NONE",
        "independent_reviewer": "NOT_STARTED",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "next_action": "Await externally appointed authority and independent reviewer; receive and verify a decision record before any authorization decision.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Export blank-safe external decision lifecycle template snapshot")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = export(args.output.resolve())
    print(
        json.dumps(
            {
                "snapshot_kind": snapshot["snapshot_kind"],
                "lifecycle_state": snapshot["lifecycle_state"],
                "record_template_sha256": snapshot["record_template_sha256"],
                "authorization_promoted": snapshot["authorization_promoted"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
