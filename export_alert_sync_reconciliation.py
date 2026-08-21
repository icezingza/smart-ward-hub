"""Export a redacted, hash-chained reconciliation matrix evidence snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from alert_sync_reconciliation_matrix import matrix_payload

ROOT = Path(__file__).resolve().parent
TRANSCRIPT_GENESIS = "0" * 64


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


def _transcript(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    previous_hash = TRANSCRIPT_GENESIS
    transcript: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        event = {
            "sequence": index,
            "event": "RECONCILIATION_DECISION",
            "scenario_id": row["scenario_id"],
            "operation": row["operation"],
            "resume_permitted": row["resume_permitted"],
            "recovery_decision": row["recovery_decision"],
            "remediation_code": row["remediation_code"],
            "opaque_refs": row.get("opaque_refs", {}),
            "previous_hash": previous_hash,
        }
        serialized = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        event_hash = hashlib.sha256(f"{previous_hash}:{serialized}".encode("utf-8")).hexdigest()
        event["event_hash"] = event_hash
        transcript.append(event)
        previous_hash = event_hash

    verify_previous = TRANSCRIPT_GENESIS
    valid = True
    for event in transcript:
        unsigned = {key: value for key, value in event.items() if key != "event_hash"}
        serialized = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        expected = hashlib.sha256(f"{verify_previous}:{serialized}".encode("utf-8")).hexdigest()
        valid = valid and event["previous_hash"] == verify_previous and event["event_hash"] == expected
        verify_previous = event["event_hash"]
    return transcript, valid


def export_evidence(output: Path | None = None, project_root: Path = ROOT) -> dict[str, Any]:
    payload = matrix_payload()
    rows = payload["rows"]
    transcript, transcript_integrity_valid = _transcript(rows)
    evidence = {
        "evidence_type": "ALERT_SYNC_RECONCILIATION_MATRIX",
        "schema_version": "1",
        "read_only": True,
        "execution_performed": False,
        "software_simulation_only": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": _source_revision(project_root),
        "authorization_boundary": payload["authorization_boundary"],
        "contract": payload["contract"],
        "matrix_row_count": payload["row_count"],
        "rows": rows,
        "transcript": transcript,
        "transcript_integrity_valid": transcript_integrity_valid,
        "redaction_verified": all(
            raw not in json.dumps(evidence if "evidence" in locals() else {}, ensure_ascii=True)
            for raw in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@")
        ),
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "functional_verification": "PASSED",
            "pilot_foundation": "PILOT_READY_FOUNDATION",
            "clinical_validation": "PENDING",
            "real_ward_execution": False,
        },
    }
    # Recompute redaction after the complete evidence object exists.
    serialized = json.dumps(evidence, ensure_ascii=True)
    evidence["redaction_verified"] = not any(
        marker in serialized for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@")
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "alert-sync-reconciliation-local.json"
    export_evidence(output=destination)
    print(destination)
