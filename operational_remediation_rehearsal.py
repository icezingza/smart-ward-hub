from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from operational_thresholds import evaluate_thresholds


SCHEMA_VERSION = "smart-ward-operational-remediation-v1"
SCENARIO_TIME = "2026-08-22T00:00:00Z"
OPAQUE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
RAW_MARKER = re.compile(r"(?i)(hn[-_]?\d|an[-_]?\d|patient[_-]?id|patient[_-]?token|@|-----BEGIN)")
RESUME_CONFIRMATION = "I_UNDERSTAND_SOFTWARE_REHEARSAL_RESUME"

REMEDIATION_ACTIONS: dict[str, str] = {
    "BACKUP_STALE": "pause_resume_and_create_verified_backup",
    "CHECKPOINT_STALE": "pause_resume_and_verify_checkpoint",
    "SYNC_BACKLOG_OVER_LIMIT": "reconcile_sync_queue_before_resume",
    "SYNC_BACKLOG_NOT_COLLECTED": "collect_sync_backlog_evidence_before_resume",
    "WORKER_QUEUE_BACKLOG_OVER_LIMIT": "reconcile_worker_queue_before_resume",
    "WORKER_QUEUE_BACKLOG_NOT_COLLECTED": "collect_worker_queue_evidence_before_resume",
    "UNRESOLVED_ALERTS_OVER_LIMIT": "route_alerts_to_manual_clinical_workflow",
    "UNRESOLVED_ALERTS_NOT_COLLECTED": "collect_alert_queue_evidence_before_resume",
    "DATABASE_NOT_VERIFIED": "run_database_integrity_and_wal_check",
    "PREFLIGHT_NOT_PASS": "stop_and_correct_preflight_configuration",
    "DISK_HEADROOM_LOW": "stop_ingestion_and_free_or_expand_storage",
    "DISK_HEADROOM_UNVERIFIED": "collect_disk_headroom_evidence",
}


class RemediationError(ValueError):
    pass


def _assert_ref(value: str, field: str) -> str:
    if not isinstance(value, str) or not OPAQUE_REF.fullmatch(value) or RAW_MARKER.search(value):
        raise RemediationError(f"{field}_must_be_opaque_reference")
    return value


def _hash_event(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass
class Transcript:
    correlation_id: str
    events: list[dict[str, Any]] = field(default_factory=list)

    def append(
        self,
        *,
        event_type: str,
        actor_role: str,
        decision: str,
        remediation_codes: list[str] | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        _assert_ref(self.correlation_id, "correlation_id")
        _assert_ref(actor_role, "actor_role")
        previous_hash = self.events[-1]["event_hash"] if self.events else "0" * 64
        body = {
            "schema_version": SCHEMA_VERSION,
            "event_seq": len(self.events) + 1,
            "event_type": event_type,
            "actor_role": actor_role,
            "correlation_id": self.correlation_id,
            "occurred_at": SCENARIO_TIME,
            "decision": decision,
            "remediation_codes": sorted(set(remediation_codes or [])),
            "details": dict(details or {}),
            "previous_hash": previous_hash,
        }
        serialized = json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if RAW_MARKER.search(serialized):
            raise RemediationError("raw_identity_or_secret_marker_in_transcript")
        event = dict(body)
        event["event_hash"] = _hash_event(body)
        self.events.append(event)
        return event

    def verify(self) -> bool:
        previous_hash = "0" * 64
        for index, event in enumerate(self.events, start=1):
            if event.get("event_seq") != index or event.get("previous_hash") != previous_hash:
                return False
            body = {key: value for key, value in event.items() if key != "event_hash"}
            if _hash_event(body) != event.get("event_hash"):
                return False
            if RAW_MARKER.search(json.dumps(event, ensure_ascii=True, sort_keys=True)):
                return False
            previous_hash = event["event_hash"]
        return bool(self.events)


def _authorization_locked(snapshot: Mapping[str, Any]) -> bool:
    boundary = snapshot.get("authorization_boundary")
    if not isinstance(boundary, Mapping):
        return False
    return (
        boundary.get("external_authority") == "NONE"
        and boundary.get("clinical_validation_authorized") is False
        and boundary.get("production_authorized") is False
    )


def evaluate_remediation(
    snapshot: Mapping[str, Any],
    *,
    correlation_id: str,
    operator_role: str,
    confirmation: str | None = None,
) -> dict[str, Any]:
    _assert_ref(correlation_id, "correlation_id")
    _assert_ref(operator_role, "operator_role")
    threshold = snapshot.get("threshold_evaluation")
    if not isinstance(threshold, Mapping):
        raise RemediationError("threshold_evaluation_required")
    codes = sorted({str(code) for code in threshold.get("remediation_codes", [])})
    unknown_codes = sorted(set(codes) - set(REMEDIATION_ACTIONS))
    if unknown_codes:
        raise RemediationError("unknown_remediation_code")
    if not _authorization_locked(snapshot):
        return {
            "schema_version": SCHEMA_VERSION,
            "decision": "AUTHORIZATION_BOUNDARY_VIOLATION",
            "resume_permitted": False,
            "resume_executed": False,
            "production_resume_permitted": False,
            "external_resume_permitted": False,
            "remediation_codes": ["AUTHORIZATION_BOUNDARY_VIOLATION"],
            "next_actions": ["stop_and_escalate_authorization_boundary_incident"],
            "operator_role": operator_role,
            "correlation_id": correlation_id,
        }
    if threshold.get("status") != "PASS" or threshold.get("resume_permitted") is not True:
        return {
            "schema_version": SCHEMA_VERSION,
            "decision": "RECONCILIATION_REQUIRED",
            "resume_permitted": False,
            "resume_executed": False,
            "production_resume_permitted": False,
            "external_resume_permitted": False,
            "remediation_codes": codes,
            "next_actions": [REMEDIATION_ACTIONS[code] for code in codes],
            "operator_role": operator_role,
            "correlation_id": correlation_id,
        }
    if confirmation != RESUME_CONFIRMATION:
        return {
            "schema_version": SCHEMA_VERSION,
            "decision": "OPERATOR_CONFIRMATION_REQUIRED",
            "resume_permitted": False,
            "resume_executed": False,
            "production_resume_permitted": False,
            "external_resume_permitted": False,
            "remediation_codes": [],
            "next_actions": ["obtain_explicit_operator_confirmation_for_software_rehearsal_only"],
            "operator_role": operator_role,
            "correlation_id": correlation_id,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "decision": "SOFTWARE_RESUME_ELIGIBLE",
        "resume_permitted": True,
        "resume_executed": False,
        "production_resume_permitted": False,
        "external_resume_permitted": False,
        "remediation_codes": [],
        "next_actions": ["do_not_execute_automatically; require_runtime_owner_action"],
        "operator_role": operator_role,
        "correlation_id": correlation_id,
    }


def _snapshot(*, backup_age: float, sync_backlog: int, unresolved_alerts: int) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "schema_version": "smart-ward-operational-status-v1",
        "preflight_status": "PASS",
        "authorization_boundary": {
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
        },
        "runtime": {
            "database": {"status": "PASS"},
            "checkpoint": {"status": "PRESENT", "age_seconds": 10},
            "backup": {"status": "PRESENT", "age_seconds": backup_age},
            "audit": {"status": "PRESENT", "age_seconds": 10},
            "anchor": {"status": "PRESENT", "age_seconds": 10},
            "disk": {"status": "PASS", "free_ratio": 0.90},
        },
        "optional_metrics": {
            "sync_backlog": sync_backlog,
            "worker_queue_backlog": 0,
            "unresolved_alerts": unresolved_alerts,
        },
    }
    snapshot["threshold_evaluation"] = evaluate_thresholds(snapshot, metrics=snapshot["optional_metrics"])
    return snapshot


def run_rehearsal(output: Path | None = None) -> dict[str, Any]:
    correlation_id = "remediation-rehearsal-001"
    operator_role = "control_room_coordinator"
    transcript = Transcript(correlation_id=correlation_id)
    blocked_snapshot = _snapshot(backup_age=86_401, sync_backlog=3, unresolved_alerts=2)
    blocked = evaluate_remediation(
        blocked_snapshot,
        correlation_id=correlation_id,
        operator_role=operator_role,
    )
    transcript.append(
        event_type="STATUS_OBSERVED",
        actor_role=operator_role,
        decision=blocked["decision"],
        remediation_codes=blocked["remediation_codes"],
        details={"evidence_class": "LOCAL_SOFTWARE_SIMULATION", "resume_permitted": False},
    )
    transcript.append(
        event_type="INGESTION_PAUSE_RECOMMENDED",
        actor_role=operator_role,
        decision="RECONCILIATION_REQUIRED",
        remediation_codes=blocked["remediation_codes"],
        details={"execution_performed": False, "manual_workflow_required": True},
    )
    remediated_snapshot = _snapshot(backup_age=10, sync_backlog=0, unresolved_alerts=0)
    confirmation_required = evaluate_remediation(
        remediated_snapshot,
        correlation_id=correlation_id,
        operator_role=operator_role,
    )
    transcript.append(
        event_type="REMEDIATION_EVIDENCE_RECHECKED",
        actor_role=operator_role,
        decision=confirmation_required["decision"],
        details={"threshold_status": remediated_snapshot["threshold_evaluation"]["status"], "resume_permitted": False},
    )
    eligible = evaluate_remediation(
        remediated_snapshot,
        correlation_id=correlation_id,
        operator_role=operator_role,
        confirmation=RESUME_CONFIRMATION,
    )
    transcript.append(
        event_type="SOFTWARE_RESUME_ELIGIBILITY_RECORDED",
        actor_role=operator_role,
        decision=eligible["decision"],
        details={"resume_executed": False, "production_resume_permitted": False},
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "rehearsal": "operational_remediation_rehearsal",
        "evidence_class": "LOCAL_SOFTWARE_SIMULATION",
        "scenario_time": SCENARIO_TIME,
        "correlation_id": correlation_id,
        "initial_decision": blocked,
        "post_remediation_decision": confirmation_required,
        "software_eligibility_decision": eligible,
        "transcript": transcript.events,
        "transcript_integrity_valid": transcript.verify(),
        "patient_data_used": False,
        "raw_frames_recorded": False,
        "resume_executed": False,
        "production_authorized": False,
        "clinical_validation_authorized": False,
        "external_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run read-only operational remediation rehearsal")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = run_rehearsal(args.output)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    print("OPERATIONAL_REMEDIATION_REHEARSAL_PASSED" if report["transcript_integrity_valid"] else "OPERATIONAL_REMEDIATION_REHEARSAL_FAILED")
    return 0 if report["transcript_integrity_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
