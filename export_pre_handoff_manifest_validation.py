"""Export a redacted local pre-handoff manifest validation record."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from pre_handoff_manifest_validator import validate_repository


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


def export_validation(output: Path | None = None, project_root: Path = ROOT) -> dict[str, Any]:
    validation = validate_repository(project_root)
    evidence = {
        "evidence_type": "PRE_HANDOFF_EVIDENCE_MANIFEST_VALIDATION",
        "schema_version": validation["schema_version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": _source_revision(project_root),
        "decision": validation["decision"],
        "remediation_codes": validation["remediation_codes"],
        "checks": validation["checks"],
        "snapshot_source_revision": validation["snapshot_source_revision"],
        "freeze_source_revision": validation["freeze_source_revision"],
        "origin_main_revision": validation["origin_main_revision"],
        "snapshot_relative": validation["snapshot_relative"],
        "external_gate_snapshot": validation["external_gate_snapshot"],
        "claim_boundary": validation["claim_boundary"],
        "authorization_boundary": validation["authorization_boundary"],
        "read_only": True,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
    }
    serialized = json.dumps(evidence, sort_keys=True, ensure_ascii=True)
    evidence["redaction_verified"] = not any(
        marker in serialized
        for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@")
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "pre-handoff-manifest-validation-local.json"
    export_validation(output=destination)
    print(destination)
