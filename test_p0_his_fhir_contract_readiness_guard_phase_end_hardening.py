"""Phase-end hardening gate for the local-only P0 HIS/FHIR readiness guard."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from export_p0_his_fhir_contract_readiness_guard import DEFAULT_OUTPUT, export_evidence
from p0_his_fhir_contract_readiness_guard import evaluate_contract_readiness


ROOT = Path(__file__).resolve().parent
TARGETS = [
    ROOT / "p0_his_fhir_contract_readiness_guard.py",
    ROOT / "export_p0_his_fhir_contract_readiness_guard.py",
]
FORBIDDEN_IMPORTS = {
    "requests", "httpx", "socket", "urllib", "serial", "bleak", "paho", "websockets",
    "google", "azure", "boto3", "celery", "apscheduler", "schedule", "subprocess",
}
FORBIDDEN_POSITIVE_LITERALS = {
    '"external_submission_allowed": True',
    '"external_transmission_performed": True',
    '"external_verification_performed": True',
    '"authorization_promoted": True',
    '"production_authorized": True',
    '"clinical_validation_authorized": True',
    '"purge_executed": True',
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
    print("[P0 HIS/FHIR Gate] no network/provider/transport/scheduler imports: PASSED")


def _assert_no_positive_authority_source_literals() -> None:
    for path in TARGETS:
        source = path.read_text(encoding="utf-8")
        for literal in FORBIDDEN_POSITIVE_LITERALS:
            assert literal not in source, f"positive authority literal in {path}: {literal}"
        scan_lines = [
            line for line in source.splitlines()
            if "SECRET_PATTERN" not in line and "SECRET_MARKERS" not in line
        ]
        assert SECRET_MARKERS.search("\n".join(scan_lines)) is None, f"secret marker in {path}"
    print("[P0 HIS/FHIR Gate] source boundary and secret-marker scan: PASSED")


def _assert_runtime_boundary() -> None:
    report = evaluate_contract_readiness()
    assert report["all_passed"] is True
    assert report["decision"] == "P0_HIS_FHIR_CONTRACT_SOFTWARE_VERIFIED_PENDING_EXTERNAL_DECISIONS"
    assert report["external_decision_count"] == 9
    assert report["external_submission_allowed"] is False
    assert report["external_transmission_performed"] is False
    assert report["external_verification_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["purge_executed"] is False
    assert report["patient_data_used"] is False
    assert report["raw_frames_recorded"] is False
    assert report["external_gate_snapshot"] if "external_gate_snapshot" in report else True
    boundary = report["authorization_boundary"]
    assert boundary == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    print("[P0 HIS/FHIR Gate] runtime contract and locked authority boundary: PASSED")


def _assert_export_round_trip() -> None:
    with tempfile.TemporaryDirectory(prefix="p0-his-fhir-export-") as directory:
        output = Path(directory) / "evidence.json"
        evidence = export_evidence(output)
        loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded == evidence
    assert loaded["evidence_scope"] == "LOCAL_DETERMINISTIC_FIXTURE_ONLY"
    assert loaded["all_passed"] is True
    assert loaded["external_submission_allowed"] is False
    assert loaded["external_transmission_performed"] is False
    assert loaded["external_verification_performed"] is False
    assert loaded["authorization_promoted"] is False
    assert loaded["purge_executed"] is False
    assert loaded["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    print("[P0 HIS/FHIR Gate] exporter round-trip and locked evidence boundary: PASSED")


def _assert_mutation_isolation() -> None:
    report = evaluate_contract_readiness()
    mutated = deepcopy(report)
    mutated["authorization_boundary"]["production_authorized"] = True
    mutated["success_ack_result"]["purge_executed"] = True
    fresh = evaluate_contract_readiness()
    assert fresh["authorization_boundary"]["production_authorized"] is False
    assert fresh["success_ack_result"]["purge_executed"] is False
    assert fresh["authorization_promoted"] is False
    print("[P0 HIS/FHIR Gate] returned evidence mutation cannot authorize or purge: PASSED")


def _assert_diff_check() -> None:
    result = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    print("[P0 HIS/FHIR Gate] git diff --check: PASSED")


def run() -> None:
    focused = subprocess.run(
        [sys.executable, str(ROOT / "test_p0_his_fhir_contract_readiness_guard.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert focused.returncode == 0, focused.stdout + focused.stderr
    print("[P0 HIS/FHIR Gate] focused/adversarial suite: PASSED")
    _assert_no_forbidden_imports()
    _assert_no_positive_authority_source_literals()
    _assert_runtime_boundary()
    _assert_export_round_trip()
    _assert_mutation_isolation()
    _assert_diff_check()
    print("P0_HIS_FHIR_CONTRACT_READINESS_GUARD_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
