"""Phase-end hardening gate for P1 host-hardware preparation reconciliation."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys

from export_p1_host_hardware_preparation_reconciliation import export_evidence
from p1_host_hardware_preparation_reconciliation import evaluate_host_hardware_preparation


ROOT = Path(__file__).resolve().parent
TARGETS = [
    ROOT / "p1_host_hardware_preparation_reconciliation.py",
    ROOT / "export_p1_host_hardware_preparation_reconciliation.py",
]
FOCUSED = ROOT / "test_p1_host_hardware_preparation_reconciliation.py"
FORBIDDEN_IMPORTS = {
    "requests", "httpx", "socket", "urllib", "serial", "bleak", "paho", "websockets",
    "google", "azure", "boto3", "celery", "apscheduler", "schedule", "subprocess",
}
FORBIDDEN_POSITIVE_LITERALS = {
    '"physical_execution_performed": True',
    '"production_authorized": True',
    '"clinical_validation_authorized": True',
    '"external_submission_allowed": True',
    '"external_transmission_performed": True',
    '"authorization_promoted": True',
}
SECRET_MARKERS = re.compile(r"(?:-----BEGIN|Bearer(?:\s+|[-_])\S+|private[_-]?key\s*[:=]|api[_-]?key\s*[:=])", re.IGNORECASE)


def _assert_focused() -> None:
    completed = subprocess.run(
        [sys.executable, str(FOCUSED)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    print("[P1 Host-Hardware Gate] focused/adversarial suite: PASSED")


def _assert_no_forbidden_imports() -> None:
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"), filename=str(target))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert not imported.intersection(FORBIDDEN_IMPORTS), (target, imported.intersection(FORBIDDEN_IMPORTS))
    print("[P1 Host-Hardware Gate] no network/provider/transport/scheduler side-effect imports: PASSED")


def _assert_source_boundary() -> None:
    for target in TARGETS:
        source = target.read_text(encoding="utf-8")
        for literal in FORBIDDEN_POSITIVE_LITERALS:
            assert literal not in source, (target, literal)
        scan_lines = [line for line in source.splitlines() if "SECRET_MARKER" not in line]
        assert SECRET_MARKERS.search("\n".join(scan_lines)) is None
    source = TARGETS[0].read_text(encoding="utf-8")
    assert "Acer Spin N17H2" in source
    assert "NOT_STARTED" in source
    assert "UNVERIFIED" in source
    print("[P1 Host-Hardware Gate] execution/authority/secret boundary scan: PASSED")


def _assert_runtime_boundary() -> None:
    report = evaluate_host_hardware_preparation()
    assert report["all_passed"] is True
    assert report["decision"] == "P1_HOST_HARDWARE_PREPARATION_RECONCILED_PENDING_TARGET_HOST_EVIDENCE"
    assert report["target_model"] == "Acer Spin N17H2"
    assert report["target_role"] == "FIXED_EDGE_HUB_CANDIDATE"
    assert report["host_execution_status"] == "NOT_STARTED"
    assert report["physical_validation"] == "UNVERIFIED"
    assert report["physical_execution_performed"] is False
    assert report["observed_result_count"] == 0
    assert report["real_target_host_evidence"] == "UNVERIFIED"
    assert report["clinical_validation"] == "PENDING"
    assert report["external_submission_allowed"] is False
    assert report["external_transmission_performed"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["external_authority"] == "NONE"
    assert report["clinical_validation_authorized"] is False
    assert report["production_authorized"] is False
    assert report["runtime_authority"] == "NONE"
    assert report["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert report["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    print("[P1 Host-Hardware Gate] runtime/cross-artifact boundary: PASSED")


def _assert_export_round_trip() -> None:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="p1-host-hardware-reconciliation-export-") as directory:
        output = Path(directory) / "evidence.json"
        evidence = export_evidence(output)
        loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded == evidence
    assert loaded["evidence_scope"] == "LOCAL_DETERMINISTIC_RECONCILIATION_ONLY"
    assert loaded["all_passed"] is True
    assert loaded["target_model"] == "Acer Spin N17H2"
    assert loaded["host_execution_status"] == "NOT_STARTED"
    assert loaded["physical_execution_performed"] is False
    assert loaded["ready_for_target_host_execution"] is False
    assert loaded["real_target_host_evidence"] == "UNVERIFIED"
    assert loaded["external_submission_allowed"] is False
    assert loaded["authorization_promoted"] is False
    assert loaded["redaction_verified"] is True
    assert loaded["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    print("[P1 Host-Hardware Gate] exporter round-trip and no target-host claim: PASSED")


def _assert_mutation_isolation() -> None:
    report = evaluate_host_hardware_preparation()
    mutated = deepcopy(report)
    mutated["target_model"] = "BMAX i11_s"
    mutated["host_execution_status"] = "EXECUTED"
    mutated["physical_execution_performed"] = True
    mutated["authorization_boundary"]["production_authorized"] = True
    mutated["external_gate_snapshot"]["passed"] = 10
    fresh = evaluate_host_hardware_preparation()
    assert fresh["target_model"] == "Acer Spin N17H2"
    assert fresh["host_execution_status"] == "NOT_STARTED"
    assert fresh["physical_execution_performed"] is False
    assert fresh["authorization_boundary"]["production_authorized"] is False
    assert fresh["external_gate_snapshot"]["passed"] == 0
    print("[P1 Host-Hardware Gate] returned evidence mutation isolation: PASSED")


def _assert_json_serializable() -> None:
    report = evaluate_host_hardware_preparation()
    encoded = json.dumps(report, ensure_ascii=True, sort_keys=True)
    assert "patient_token" not in encoded
    assert "patient_id" not in encoded
    assert "-----BEGIN" not in encoded
    assert "Acer Spin N17H2" in encoded
    print("[P1 Host-Hardware Gate] JSON serialization and zero-PII markers: PASSED")


def _assert_diff_check() -> None:
    completed = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    print("[P1 Host-Hardware Gate] git diff --check: PASSED")


def run() -> None:
    _assert_focused()
    _assert_no_forbidden_imports()
    _assert_source_boundary()
    _assert_runtime_boundary()
    _assert_export_round_trip()
    _assert_mutation_isolation()
    _assert_json_serializable()
    _assert_diff_check()
    print("P1_HOST_HARDWARE_PREPARATION_RECONCILIATION_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
