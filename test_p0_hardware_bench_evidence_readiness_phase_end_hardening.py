"""Phase-end hardening gate for local-only hardware-bench evidence readiness."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from export_p0_hardware_bench_evidence_readiness import export_evidence
from p0_hardware_bench_evidence_readiness import evaluate_hardware_bench_readiness


ROOT = Path(__file__).resolve().parent
TARGETS = [
    ROOT / "p0_hardware_bench_evidence_readiness.py",
    ROOT / "export_p0_hardware_bench_evidence_readiness.py",
]
FORBIDDEN_IMPORTS = {
    "requests", "httpx", "socket", "urllib", "serial", "bleak", "paho", "websockets",
    "google", "azure", "boto3", "celery", "apscheduler", "schedule", "subprocess",
}
FORBIDDEN_POSITIVE_LITERALS = {
    '"physical_execution_performed": True',
    '"clinical_use_authorized": True',
    '"external_submission_allowed": True',
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
    print("[P0 Hardware Bench Gate] no network/provider/transport/scheduler imports: PASSED")


def _assert_source_boundary() -> None:
    for path in TARGETS:
        source = path.read_text(encoding="utf-8")
        for literal in FORBIDDEN_POSITIVE_LITERALS:
            assert literal not in source, f"positive execution/authority literal in {path}: {literal}"
        scan_lines = [
            line for line in source.splitlines()
            if "SECRET_MARKER" not in line and "SECRET_MARKERS" not in line
        ]
        assert SECRET_MARKERS.search("\n".join(scan_lines)) is None, f"secret marker in {path}"
    print("[P0 Hardware Bench Gate] source execution/authority and secret scan: PASSED")


def _assert_runtime_boundary() -> None:
    report = evaluate_hardware_bench_readiness()
    assert report["all_passed"] is True
    assert report["decision"] == "P0_HARDWARE_BENCH_PACKET_PREPARED_PENDING_PHYSICAL_EXECUTION"
    assert report["mode"] == "LOCAL_DETERMINISTIC_TEMPLATE_ONLY"
    assert report["target_model"] == "Acer Spin N17H2"
    assert report["target_role"] == "FIXED_EDGE_HUB_CANDIDATE"
    assert report["packet_status"] == "PREPARED_NOT_EXECUTED"
    assert report["physical_execution_performed"] is False
    assert report["physical_hardware_evidence"] == "UNVERIFIED"
    assert report["observed_result_count"] == 0
    assert report["clinical_use_authorized"] is False
    assert report["external_submission_allowed"] is False
    assert report["external_transmission_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    boundary = report["authorization_boundary"]
    assert boundary == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    print("[P0 Hardware Bench Gate] packet status and locked authority boundary: PASSED")


def _assert_export_round_trip() -> None:
    with tempfile.TemporaryDirectory(prefix="p0-hardware-bench-export-") as directory:
        output = Path(directory) / "evidence.json"
        evidence = export_evidence(output)
        loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded == evidence
    assert loaded["evidence_scope"] == "LOCAL_DETERMINISTIC_TEMPLATE_ONLY"
    assert loaded["all_passed"] is True
    assert loaded["packet_status"] == "PREPARED_NOT_EXECUTED"
    assert loaded["physical_execution_performed"] is False
    assert loaded["clinical_use_authorized"] is False
    assert loaded["external_submission_allowed"] is False
    assert loaded["authorization_promoted"] is False
    assert loaded["redaction_verified"] is True
    assert loaded["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    print("[P0 Hardware Bench Gate] exporter round-trip and frozen-evidence safety: PASSED")


def _assert_mutation_isolation() -> None:
    report = evaluate_hardware_bench_readiness()
    mutated = deepcopy(report)
    mutated["physical_execution_performed"] = True
    mutated["clinical_use_authorized"] = True
    mutated["authorization_boundary"]["production_authorized"] = True
    fresh = evaluate_hardware_bench_readiness()
    assert fresh["physical_execution_performed"] is False
    assert fresh["clinical_use_authorized"] is False
    assert fresh["authorization_boundary"]["production_authorized"] is False
    assert fresh["authorization_promoted"] is False
    print("[P0 Hardware Bench Gate] returned evidence mutation cannot execute or authorize: PASSED")


def _assert_diff_check() -> None:
    result = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    print("[P0 Hardware Bench Gate] git diff --check: PASSED")


def run() -> None:
    focused = subprocess.run(
        [sys.executable, str(ROOT / "test_p0_hardware_bench_evidence_readiness.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert focused.returncode == 0, focused.stdout + focused.stderr
    print("[P0 Hardware Bench Gate] focused/adversarial suite: PASSED")
    _assert_no_forbidden_imports()
    _assert_source_boundary()
    _assert_runtime_boundary()
    _assert_export_round_trip()
    _assert_mutation_isolation()
    _assert_diff_check()
    print("P0_HARDWARE_BENCH_EVIDENCE_READINESS_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
