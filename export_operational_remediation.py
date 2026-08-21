from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from operational_remediation_rehearsal import RAW_MARKER, run_rehearsal


EXPORT_SCHEMA_VERSION = "smart-ward-operational-remediation-evidence-v1"
ROOT = Path(__file__).resolve().parent


def _source_revision(project_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE"
    value = completed.stdout.strip().lower()
    return value if len(value) == 40 and all(char in "0123456789abcdef" for char in value) else "UNAVAILABLE"


def export_evidence(*, output: Path, project_root: Path = ROOT) -> dict[str, Any]:
    report = run_rehearsal()
    exported = {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "source_revision": _source_revision(project_root.resolve()),
        "evidence_class": "LOCAL_SOFTWARE_SIMULATION",
        "export_kind": "OPERATIONAL_REMEDIATION_TRANSCRIPT",
        "read_only": True,
        "execution_performed": False,
        "redaction_verified": True,
        "report": report,
    }
    encoded = json.dumps(exported, ensure_ascii=True, sort_keys=True)
    if RAW_MARKER.search(encoded):
        raise ValueError("redaction_marker_detected")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(exported, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exported


def main() -> int:
    parser = argparse.ArgumentParser(description="Export redacted operational remediation evidence")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args()
    evidence = export_evidence(output=args.output, project_root=args.project_root)
    print(
        json.dumps(
            {
                "export_schema_version": evidence["export_schema_version"],
                "evidence_class": evidence["evidence_class"],
                "source_revision": evidence["source_revision"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
