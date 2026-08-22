"""Phase-end hardening gate for local-only P0 identity/transport readiness."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from export_p0_identity_transport_readiness_guard import export_evidence
from p0_identity_transport_readiness_guard import evaluate_identity_transport_readiness


ROOT = Path(__file__).resolve().parent
TARGETS = [
    ROOT / "p0_identity_transport_readiness_guard.py",
    ROOT / "export_p0_identity_transport_readiness_guard.py",
]
FORBIDDEN_IMPORTS = {
    "requests", "httpx", "socket", "urllib", "serial", "bleak", "paho", "websockets",
    "google", "azure", "boto3", "celery", "apscheduler", "schedule", "subprocess",
}
FORBIDDEN_POSITIVE_LITERALS = {
    '"external_submission_allowed": True',
    '"external_transmission_performed": True',
    '"authorization_promoted": True',
    '"production_authorized": True',
    '"clinical_validation_authorized": True',
    '"live_handshake_verified": True',
    '"live_rotation_verified": True',
    '"live_revocation_verified": True',
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
    print("[P0 Identity/Transport Gate] no network/provider/transport/scheduler imports: PASSED")


def _assert_source_boundary() -> None:
    for path in TARGETS:
        source = path.read_text(encoding="utf-8")
        for literal in FORBIDDEN_POSITIVE_LITERALS:
            assert literal not in source, f"positive live/authority literal in {path}: {literal}"
        scan_lines = [
            line for line in source.splitlines()
            if "SECRET_PATTERN" not in line and "SECRET_MARKER" not in line and "SECRET_MARKERS" not in line
        ]
        assert SECRET_MARKERS.search("\n".join(scan_lines)) is None, f"secret marker in {path}"
    print("[P0 Identity/Transport Gate] source live-evidence and secret-marker scan: PASSED")


def _assert_runtime_boundary() -> None:
    report = evaluate_identity_transport_readiness()
    assert report["all_passed"] is True
    assert report["decision"] == "P0_IDENTITY_TRANSPORT_SOFTWARE_VERIFIED_PENDING_LIVE_EVIDENCE"
    assert report["external_submission_allowed"] is False
    assert report["external_transmission_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["production_authorized"] is False
    assert report["clinical_validation_authorized"] is False
    assert report["external_authority"] == "NONE"
    assert report["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    assert all(value == "UNVERIFIED" for value in report["live_evidence"].values())
    boundary = report["authorization_boundary"]
    assert boundary == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    print("[P0 Identity/Transport Gate] runtime and authority boundary: PASSED")


def _assert_export_round_trip() -> None:
    with tempfile.TemporaryDirectory(prefix="p0-identity-transport-export-") as directory:
        output = Path(directory) / "evidence.json"
        evidence = export_evidence(output)
        loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded == evidence
    assert loaded["evidence_scope"] == "LOCAL_DETERMINISTIC_FIXTURE_ONLY"
    assert loaded["all_passed"] is True
    assert loaded["external_submission_allowed"] is False
    assert loaded["external_transmission_performed"] is False
    assert loaded["authorization_promoted"] is False
    assert loaded["redaction_verified"] is True
    assert loaded["external_gate_snapshot"] == {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0}
    print("[P0 Identity/Transport Gate] exporter round-trip and frozen-evidence safety: PASSED")


def _assert_mutation_isolation() -> None:
    report = evaluate_identity_transport_readiness()
    mutated = deepcopy(report)
    mutated["authorization_boundary"]["production_authorized"] = True
    mutated["live_evidence"]["mutual_tls_handshake"] = "VERIFIED"
    fresh = evaluate_identity_transport_readiness()
    assert fresh["authorization_boundary"]["production_authorized"] is False
    assert fresh["live_evidence"]["mutual_tls_handshake"] == "UNVERIFIED"
    assert fresh["authorization_promoted"] is False
    print("[P0 Identity/Transport Gate] returned evidence mutation is isolated: PASSED")


def _assert_diff_check() -> None:
    result = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    print("[P0 Identity/Transport Gate] git diff --check: PASSED")


def run() -> None:
    focused = subprocess.run(
        [sys.executable, str(ROOT / "test_p0_identity_transport_readiness_guard.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert focused.returncode == 0, focused.stdout + focused.stderr
    print("[P0 Identity/Transport Gate] focused/adversarial suite: PASSED")
    _assert_no_forbidden_imports()
    _assert_source_boundary()
    _assert_runtime_boundary()
    _assert_export_round_trip()
    _assert_mutation_isolation()
    _assert_diff_check()
    print("P0_IDENTITY_TRANSPORT_READINESS_GUARD_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
