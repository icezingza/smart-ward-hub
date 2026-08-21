from __future__ import annotations

import argparse
import json
from pathlib import Path

from wave1_external_evidence_intake import canonical_sha256, template, validate


def export(output: Path) -> dict:
    payload = template()
    validation = validate(payload, template_only=True)
    snapshot = {
        "schema_version": payload["schema_version"],
        "package_id": payload["package_id"],
        "project": payload["project"],
        "repository": payload["repository"],
        "readiness": payload["readiness"],
        "submission_status": payload["submission_status"],
        "execution_status": payload["execution_status"],
        "external_execution_authorized": payload["external_execution_authorized"],
        "production_authorized": payload["production_authorized"],
        "clinical_validation_authorized": payload["clinical_validation_authorized"],
        "independent_verification_required": payload["independent_verification_required"],
        "evidence_class": payload["evidence_class"],
        "authorization_boundary": payload["authorization_boundary"],
        "prerequisite_count": len(payload["prerequisites"]),
        "missing_external_prerequisites": [item["prerequisite_id"] for item in payload["prerequisites"]],
        "validation": validation,
        "template_sha256": canonical_sha256(payload),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Wave 1 external evidence intake snapshot")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = export(args.output.resolve())
    print(
        json.dumps(
            {
                "readiness": snapshot["readiness"],
                "execution_status": snapshot["execution_status"],
                "prerequisite_count": snapshot["prerequisite_count"],
                "missing_count": len(snapshot["missing_external_prerequisites"]),
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
