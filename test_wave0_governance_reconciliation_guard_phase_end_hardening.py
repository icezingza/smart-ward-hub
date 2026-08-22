"""Phase-end hardening gate for Wave 0 governance reconciliation."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys

from export_wave0_governance_reconciliation_guard import export_evidence
from wave0_governance_reconciliation_guard import evaluate_wave0_governance_reconciliation


ROOT = Path(__file__).resolve().parent
TARGETS = [
    ROOT / "wave0_governance_reconciliation_guard.py",
    ROOT / "export_wave0_governance_reconciliation_guard.py",
]
FOCUSED = ROOT / "test_wave0_governance_reconciliation_guard.py"
FORBIDDEN_IMPORTS = {
    "requests", "httpx", "socket", "urllib", "serial", "bleak", "paho", "websockets",
    "google", "azure", "boto3", "celery", "apscheduler", "schedule", "subprocess",
}
FORBIDDEN_POSITIVE_LITERALS = {
    '"appointment_confirmed": True',
    '"ready_for_external_review": True',
    '"submission_allowed": True',
    '"external_transmission_performed": True',
    '"authorization_promoted": True',
    '"production_authorized": True',
    '"clinical_validation_authorized": True',
}
SECRET_MARKERS = re.compile(r"(?:-----BEGIN|Bearer(?:\s+|[-_])\S+|private[_-]?key\s*[:=]|api[_-]?key\s*[:=])", re.IGNORECASE)


def _assert_no_forbidden_imports() -> None:
    for path in TARGETS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".", 1)[0]}
            else:
                continue
            assert not names.intersection(FORBIDDEN_IMPORTS), f"forbidden import in {path}"
    print("[Wave 0 Reconciliation Gate] no network/provider/transport/scheduler imports: PASSED")


def _assert_source_boundary() -> None:
    for path in TARGETS:
        source = path.read_text(encoding="utf-8")
        for literal in FORBIDDEN_POSITIVE_LITERALS:
            assert literal not in source, f"positive appointment/authority literal in {path}: {literal}"
        scan_lines = [
            line for line in source.splitlines()
            if "SECRET_MARKER" not in line and "SECRET_MARKERS" not in line
        ]
        assert SECRET_MARKERS.search("\n".join(scan_lines)) is None, f"secret marker in {path}"
    print("[Wave 0 Reconciliation Gate] appointment-promotion and secret scan: PASSED")


def _assert_runtime_boundary() -> None:
    report = evaluate_wave0_governance_reconciliation()
    assert report["all_passed"] is True
    assert report["decision"] == "WAVE0_GOVERNANCE_RECONCILED_READY_FOR_EXTERNAL_APPOINTMENT_ONLY"
    assert report["ready_for_external_appointment"] is True
    assert report["ready_for_external_review"] is False
    assert report["appointment_confirmed"] is False
    assert report["submission_allowed"] is False
    assert report["external_transmission_performed"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["external_authority"] == "NONE"
    assert report["clinical_validation_authorized"] is False
    assert report["production_authorized"] is False
    assert report["runtime_authority"] == "NONE"
    assert report["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert report["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    gate_result = report["external_gate_reconciliation"]
    assert gate_result["status_counts"] == {"BLOCKED": 7, "OPEN": 3, "EVIDENCE_SUBMITTED": 0, "TOTAL": 10}
    assert len(gate_result["blocked_gate_ids"]) == 7
    assert len(gate_result["open_gate_ids"]) == 3
    assert gate_result["evidence_submitted_gate_ids"] == []
    assert report["appointment_templates"]["appointment_decision"] == "NOT_ISSUED"
    assert report["appointment_templates"]["reviewer_appointment"] == "PENDING_EXTERNAL_APPOINTMENT"
    print("[Wave 0 Reconciliation Gate] runtime, appointment and gate boundaries: PASSED")


def _assert_export_round_trip() -> None:
    with __import__("tempfile").TemporaryDirectory(prefix="wave0-governance-reconciliation-export-") as directory:
        output = Path(directory) / "evidence.json"
        evidence = export_evidence(output)
        loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded == evidence
    assert loaded["evidence_scope"] == "LOCAL_DETERMINISTIC_RECONCILIATION_ONLY"
    assert loaded["all_passed"] is True
    assert loaded["ready_for_external_appointment"] is True
    assert loaded["ready_for_external_review"] is False
    assert loaded["appointment_confirmed"] is False
    assert loaded["submission_allowed"] is False
    assert loaded["external_transmission_performed"] is False
    assert loaded["authorization_promoted"] is False
    assert loaded["redaction_verified"] is True
    assert loaded["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    print("[Wave 0 Reconciliation Gate] exporter round-trip and no-appointment export: PASSED")


def _assert_mutation_isolation() -> None:
    report = evaluate_wave0_governance_reconciliation()
    mutated = deepcopy(report)
    mutated["ready_for_external_review"] = True
    mutated["appointment_confirmed"] = True
    mutated["submission_allowed"] = True
    mutated["authorization_boundary"]["production_authorized"] = True
    mutated["external_gate_snapshot"]["passed"] = 10
    fresh = evaluate_wave0_governance_reconciliation()
    assert fresh["ready_for_external_review"] is False
    assert fresh["appointment_confirmed"] is False
    assert fresh["submission_allowed"] is False
    assert fresh["authorization_boundary"]["production_authorized"] is False
    assert fresh["external_gate_snapshot"]["passed"] == 0
    assert fresh["authorization_promoted"] is False
    print("[Wave 0 Reconciliation Gate] returned evidence mutation is isolated: PASSED")


def _assert_focused() -> None:
    completed = subprocess.run(
        [sys.executable, str(FOCUSED)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    print("[Wave 0 Reconciliation Gate] focused/adversarial suite: PASSED")


def _assert_diff_check() -> None:
    completed = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    print("[Wave 0 Reconciliation Gate] git diff --check: PASSED")


def run() -> None:
    _assert_focused()
    _assert_no_forbidden_imports()
    _assert_source_boundary()
    _assert_runtime_boundary()
    _assert_export_round_trip()
    _assert_mutation_isolation()
    _assert_diff_check()
    print("WAVE0_GOVERNANCE_RECONCILIATION_GUARD_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
