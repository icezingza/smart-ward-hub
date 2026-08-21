from __future__ import annotations

import json
from pathlib import Path
import tempfile

from software_rollback_rehearsal import SCHEMA_VERSION, run_rehearsal


ROOT = Path(__file__).resolve().parent


def run() -> None:
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rollback-rehearsal.json"
        report = run_rehearsal(output)
        assert output.is_file()
        assert json.loads(output.read_text(encoding="utf-8")) == report

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["mode"] == "isolated_nonproduction_targets"
    assert report["evidence_class"] == "LOCAL_SOFTWARE_SIMULATION"
    assert report["drift_simulated_after_backup"] is True
    assert report["audit_exported_before_restore"] is True
    assert report["anchor_exported_before_restore"] is True
    assert report["decision"] == "ROLLBACK_VERIFIED_IN_ISOLATED_TARGET"
    assert report["checks"]["all_post_restore_checks_passed"] is True
    assert report["checks"]["resume_permitted_in_software_rehearsal"] is True
    assert report["checks"]["production_resume_permitted"] is False
    assert report["checks"]["external_resume_permitted"] is False
    assert report["checks"]["database"]["journal_mode"] == "wal"
    assert report["checks"]["database"]["integrity_check"] == "ok"
    assert report["checks"]["checkpoint"]["last_sequence"] == 2
    assert report["checks"]["audit_export"]["redaction_shape_valid"] is True
    assert report["checks"]["anchor"]["receipt_readback_valid"] is True
    assert report["checks"]["worker_queue"]["status"] == "QUEUED"
    assert report["checks"]["worker_queue"]["stale_status_before_reconciliation"] == "RUNNING"
    assert report["checks"]["worker_stale_lease_recovery"]["blocked_jobs"] == ["rollback-worker-stale"]
    assert report["checks"]["worker_stale_lease_recovery"]["reconciled_status"] == "FAILED"
    assert report["checks"]["worker_stale_lease_recovery"]["audit_chain_valid"] is True
    fault_results = report["fault_injection_results"]
    assert all(item["passed"] is True for item in fault_results.values())
    assert all(item["resume_permitted"] is False for item in fault_results.values())
    assert fault_results["partial_audit_write"]["partial_write_detected"] is True
    assert "BACKUP_STALE" in fault_results["backup_freshness_breach"]["remediation_codes"]
    assert fault_results["schema_migration_mismatch"]["observed_user_version"] == 8
    assert report["patient_data_used"] is False
    assert report["raw_frames_recorded"] is False
    assert report["external_authority"] == "NONE"
    assert report["clinical_validation_authorized"] is False
    assert report["production_authorized"] is False

    encoded = json.dumps(report, ensure_ascii=True)
    for marker in ("patient_token", "patient_id", "HN-", "secret", "PRIVATE KEY"):
        assert marker not in encoded
    print("[Rollback] isolated target restore, drift rollback and post-restore checks: PASSED")
    print("[Rollback] software-only and no-production-resume boundary: PASSED")
    print("SOFTWARE_ROLLBACK_REHEARSAL_TESTS_PASSED")


if __name__ == "__main__":
    run()
