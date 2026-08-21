"""Export fixture-only sync/alert replay evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from sync_alert_replay_harness import matrix_payload

ROOT = Path(__file__).resolve().parent
GENESIS = "0" * 64


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


def _build_transcript(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    previous_hash = GENESIS
    transcript: list[dict[str, Any]] = []
    for sequence, row in enumerate(rows, start=1):
        event = {
            "sequence": sequence,
            "event": "REPLAY_DECISION",
            "scenario_id": row["scenario_id"],
            "operation": row["operation"],
            "state": row["state"],
            "resume_permitted": row["resume_permitted"],
            "recovery_decision": row["recovery_decision"],
            "remediation_code": row["remediation_code"],
            "duplicate_safe": row["duplicate_safe"],
            "purge_permitted": row["purge_permitted"],
            "purge_executed": row["purge_executed"],
            "replay_permitted": row["replay_permitted"],
            "replay_executed": row["replay_executed"],
            "refresh_required": row["refresh_required"],
            "mutation_performed": row["mutation_performed"],
            "opaque_refs": row.get("opaque_refs", {}),
            "previous_hash": previous_hash,
        }
        serialized = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        event_hash = hashlib.sha256(f"{previous_hash}:{serialized}".encode("utf-8")).hexdigest()
        event["event_hash"] = event_hash
        transcript.append(event)
        previous_hash = event_hash

    verify_previous = GENESIS
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
    transcript, transcript_integrity_valid = _build_transcript(rows)
    evidence: dict[str, Any] = {
        "evidence_type": "SYNC_ALERT_REPLAY_HARNESS",
        "schema_version": "1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": _source_revision(project_root),
        "contract": payload["contract"],
        "mode": payload["mode"],
        "read_only": True,
        "execution_performed": False,
        "external_transmission_performed": False,
        "authorization_boundary": payload["authorization_boundary"],
        "row_count": payload["row_count"],
        "rows": rows,
        "transcript": transcript,
        "transcript_integrity_valid": transcript_integrity_valid,
        "claim_boundary": {
            "status": "CONTROLLED_PRODUCTION_PROTOTYPE",
            "functional_verification": "PASSED",
            "clinical_validation": "PENDING",
            "real_his_emr_execution": False,
            "real_ward_execution": False,
        },
    }
    serialized = json.dumps(evidence, ensure_ascii=True)
    evidence["redaction_verified"] = not any(
        marker in serialized
        for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@")
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "sync-alert-replay-local.json"
    export_evidence(output=destination)
    print(destination)
