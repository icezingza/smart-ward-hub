"""Export the consolidated internal handoff index as local redacted evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from consolidated_internal_handoff_index import build_index

ROOT = Path(__file__).resolve().parent


def _source_revision(project_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"


def export_index(output: Path | None = None, project_root: Path = ROOT) -> dict[str, Any]:
    result = build_index(project_root)
    evidence = {
        "evidence_type": "CONSOLIDATED_INTERNAL_HANDOFF_INDEX",
        "schema_version": result.index["schema_version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": _source_revision(project_root),
        "decision": result.decision,
        "remediation_codes": list(result.remediation_codes),
        "index": result.index,
        "read_only": True,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "authorization_boundary": result.index["authorization_boundary"],
        "claim_boundary": result.index["claim_boundary"],
    }
    serialized = json.dumps(evidence, sort_keys=True, ensure_ascii=True)
    evidence["redaction_verified"] = not any(
        marker in serialized
        for marker in (
            "HN-",
            "AN-",
            "patient_id",
            "patient_token",
            "PRIVATE KEY",
            "@",
        )
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "consolidated-internal-handoff-index-local.json"
    export_index(output=destination)
    print(destination)
