"""Export operator approval/read-back evidence without authorizing execution."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from worker_recovery_approval import build_approval_readback

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


def export_evidence(output: Path | None = None, project_root: Path = ROOT) -> dict[str, Any]:
    report = build_approval_readback()
    evidence: dict[str, Any] = {
        "evidence_type": "WORKER_RECOVERY_OPERATOR_APPROVAL_READBACK",
        "schema_version": report["schema_version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": _source_revision(project_root),
        "approval": report["approval"],
        "validation": report["validation"],
        "transcript_integrity_valid": report["transcript_integrity_valid"],
        "read_only": report["read_only"],
        "replay_executed": report["replay_executed"],
        "authorization_boundary": {
            "external_authority": report["external_authority"],
            "clinical_validation_authorized": report["clinical_validation_authorized"],
            "production_authorized": report["production_authorized"],
            "runtime_authority": report["runtime_authority"],
            "pilot_gate_status": report["pilot_gate_status"],
        },
        "claim_boundary": report["claim_boundary"],
    }
    serialized = json.dumps(evidence, sort_keys=True, ensure_ascii=True)
    evidence["redaction_verified"] = not any(
        marker in serialized
        for marker in (
            "HN-",
            "AN-",
            "patient_id",
            "patient_token",
            "job-lease-opaque-001",
            "worker-opaque-a",
            "reconcile-opaque-lease-001",
            "PRIVATE KEY",
            "@",
        )
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "worker-recovery-approval-local.json"
    export_evidence(output=destination)
    print(destination)
