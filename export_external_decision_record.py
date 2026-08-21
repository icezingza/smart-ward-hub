from __future__ import annotations

import argparse
import json
from pathlib import Path

from external_decision_record import canonical_sha256, template, validate


def export(output: Path) -> dict:
    payload = template()
    validation = validate(payload, template_only=True)
    snapshot = {
        "schema_version": payload["schema_version"],
        "project": payload["project"],
        "repository": payload["repository"],
        "status": payload["status"],
        "evidence_class": payload["evidence_class"],
        "decision": payload["decision"],
        "external_decision_verified": payload["external_decision_verified"],
        "authorization_promoted": payload["authorization_promoted"],
        "external_execution_authorized": payload["external_execution_authorized"],
        "production_authorized": payload["production_authorized"],
        "clinical_validation_authorized": payload["clinical_validation_authorized"],
        "authorization_boundary": payload["authorization_boundary"],
        "validation": validation,
        "template_sha256": canonical_sha256(payload),
        "next_action": "Await an externally appointed authority and independently verified decision record; do not authorize locally.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Export blank-safe external decision record template")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = export(args.output.resolve())
    print(
        json.dumps(
            {
                "status": snapshot["status"],
                "decision": snapshot["decision"],
                "authorization_promoted": snapshot["authorization_promoted"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
