"""Export a redacted operator-facing worker recovery transcript."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from worker_recovery_transcript import build_worker_recovery_transcript

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
    report = build_worker_recovery_transcript()
    evidence: dict[str, Any] = {
        "evidence_type": "OPERATOR_WORKER_RECOVERY_TRANSCRIPT",
        "schema_version": report["schema_version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": _source_revision(project_root),
        "evidence_class": report["evidence_class"],
        "correlation_ref": report["correlation_ref"],
        "operator_role": report["operator_role"],
        "transcript": report["transcript"],
        "transcript_integrity_valid": report["transcript_integrity_valid"],
        "read_only": report["read_only"],
        "execution_performed": report["execution_performed"],
        "replay_executed": report["replay_executed"],
        "raw_worker_identifiers_exported": report["raw_worker_identifiers_exported"],
        "patient_data_used": report["patient_data_used"],
        "authorization_boundary": {
            "external_authority": report["external_authority"],
            "clinical_validation_authorized": report["clinical_validation_authorized"],
            "production_authorized": report["production_authorized"],
            "runtime_authority": report["runtime_authority"],
        },
        "pilot_gate_status": report["pilot_gate_status"],
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
            "worker-opaque-a",
            "job-lease-opaque-001",
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
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "worker-recovery-transcript-local.json"
    export_evidence(output=destination)
    print(destination)
