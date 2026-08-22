"""Export a redacted internal pre-handoff readiness record."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from pre_handoff_readiness import check_pre_handoff


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


def export_readiness(output: Path | None = None, project_root: Path = ROOT) -> dict[str, Any]:
    readiness = check_pre_handoff(project_root)
    evidence = {
        "evidence_type": "PRE_HANDOFF_READINESS_CHECK",
        "schema_version": readiness["schema_version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": _source_revision(project_root),
        "decision": readiness["decision"],
        "remediation_codes": readiness["remediation_codes"],
        "checks": readiness["checks"],
        "drift_decision": readiness["drift_decision"],
        "handoff_index_decision": readiness["handoff_index_decision"],
        "freeze_source_revision": readiness["freeze_source_revision"],
        "origin_main_revision": readiness["origin_main_revision"],
        "external_gate_snapshot": readiness["external_gate_snapshot"],
        "claim_boundary": readiness["claim_boundary"],
        "authorization_boundary": readiness["authorization_boundary"],
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
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "pre-handoff-readiness-local.json"
    export_readiness(output=destination)
    print(destination)
