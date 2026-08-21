from __future__ import annotations

import json
from pathlib import Path
import tempfile

from export_operational_remediation import export_evidence
from operational_remediation_rehearsal import (
    RESUME_CONFIRMATION,
    RemediationError,
    _snapshot,
    evaluate_remediation,
    run_rehearsal,
)


ROOT = Path(__file__).resolve().parent


def run() -> None:
    blocked_snapshot = _snapshot(backup_age=86_401, sync_backlog=2, unresolved_alerts=1)
    blocked = evaluate_remediation(
        blocked_snapshot,
        correlation_id="remediation-test-001",
        operator_role="control_room_coordinator",
    )
    assert blocked["decision"] == "RECONCILIATION_REQUIRED"
    assert blocked["resume_permitted"] is False
    assert blocked["production_resume_permitted"] is False
    assert set(blocked["remediation_codes"]) == {
        "BACKUP_STALE",
        "SYNC_BACKLOG_OVER_LIMIT",
        "UNRESOLVED_ALERTS_OVER_LIMIT",
    }

    healthy_snapshot = _snapshot(backup_age=10, sync_backlog=0, unresolved_alerts=0)
    confirmation_required = evaluate_remediation(
        healthy_snapshot,
        correlation_id="remediation-test-002",
        operator_role="control_room_coordinator",
    )
    assert confirmation_required["decision"] == "OPERATOR_CONFIRMATION_REQUIRED"
    assert confirmation_required["resume_permitted"] is False
    eligible = evaluate_remediation(
        healthy_snapshot,
        correlation_id="remediation-test-002",
        operator_role="control_room_coordinator",
        confirmation=RESUME_CONFIRMATION,
    )
    assert eligible["decision"] == "SOFTWARE_RESUME_ELIGIBLE"
    assert eligible["resume_permitted"] is True
    assert eligible["resume_executed"] is False
    assert eligible["production_resume_permitted"] is False

    unsafe_snapshot = dict(healthy_snapshot)
    unsafe_snapshot["authorization_boundary"] = {
        "external_authority": "UNVERIFIED",
        "clinical_validation_authorized": True,
        "production_authorized": True,
    }
    violation = evaluate_remediation(
        unsafe_snapshot,
        correlation_id="remediation-test-003",
        operator_role="control_room_coordinator",
        confirmation=RESUME_CONFIRMATION,
    )
    assert violation["decision"] == "AUTHORIZATION_BOUNDARY_VIOLATION"
    assert violation["resume_permitted"] is False

    for bad_ref in ("HN-2026-0001", "patient_token", "operator@example.org", "bad ref"):
        try:
            evaluate_remediation(
                healthy_snapshot,
                correlation_id=bad_ref,
                operator_role="control_room_coordinator",
            )
        except RemediationError:
            pass
        else:
            raise AssertionError(f"unsafe correlation ref accepted: {bad_ref}")

    report = run_rehearsal()
    assert report["transcript_integrity_valid"] is True
    assert len(report["transcript"]) == 4
    assert report["initial_decision"]["decision"] == "RECONCILIATION_REQUIRED"
    assert report["post_remediation_decision"]["decision"] == "OPERATOR_CONFIRMATION_REQUIRED"
    assert report["software_eligibility_decision"]["decision"] == "SOFTWARE_RESUME_ELIGIBLE"
    assert report["resume_executed"] is False
    encoded = json.dumps(report, ensure_ascii=True)
    for marker in ("patient_id", "patient_token", "HN-", "@", "PRIVATE KEY", "secret"):
        assert marker not in encoded

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "operational-remediation.json"
        evidence = export_evidence(output=output, project_root=ROOT)
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved == evidence
        assert evidence["read_only"] is True
        assert evidence["execution_performed"] is False
        assert evidence["redaction_verified"] is True
        assert evidence["source_revision"] != "UNAVAILABLE"
        assert evidence["report"]["transcript_integrity_valid"] is True
    print("[Remediation] blocked/confirmation/eligible workflow: PASSED")
    print("[Remediation] authorization boundary, opaque refs and redaction: PASSED")
    print("[Remediation] hash-chained transcript and deterministic exporter: PASSED")
    print("OPERATIONAL_REMEDIATION_REHEARSAL_TESTS_PASSED")


if __name__ == "__main__":
    run()
