from __future__ import annotations

import json
from pathlib import Path
import tempfile

from cross_component_recovery_matrix import SCHEMA_VERSION, run_matrix


ROOT = Path(__file__).resolve().parent


def run() -> None:
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "recovery-matrix.json"
        report = run_matrix(output)
        assert output.is_file()
        assert json.loads(output.read_text(encoding="utf-8")) == report

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["mode"] == "software_fault_injection"
    assert report["evidence_class"] == "LOCAL_SOFTWARE_SIMULATION"
    assert report["all_passed"] is True
    assert report["normal_resume_after_verified_roundtrip"] is True
    assert report["resume_permitted_after_unresolved_fault"] is False
    assert report["recovery_decision_on_unverified_component"] == "RECONCILIATION_REQUIRED"
    assert report["patient_data_used"] is False
    assert report["raw_frames_recorded"] is False
    assert report["external_authority"] == "NONE"
    assert report["clinical_validation_authorized"] is False
    assert report["production_authorized"] is False
    assert report["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"

    expected = {
        "backup_restore_roundtrip",
        "database_tamper_fails_closed",
        "checkpoint_tamper_fails_closed",
        "anchor_tamper_requires_reconciliation",
        "checkpoint_corruption_isolated",
        "combined_faults_block_resume",
    }
    actual = {item["scenario"] for item in report["results"]}
    assert actual == expected
    assert all(item["status"] == "PASS" for item in report["results"])
    assert all(
        item.get("recovery_decision") == "RECONCILIATION_REQUIRED"
        for item in report["results"]
        if item["scenario"] != "backup_restore_roundtrip"
    )
    print("[Recovery Matrix] six cross-component scenarios and decision boundary: PASSED")
    print("CROSS_COMPONENT_RECOVERY_MATRIX_TESTS_PASSED")


if __name__ == "__main__":
    run()
