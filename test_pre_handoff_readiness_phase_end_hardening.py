"""Phase-end hardening gate for the internal pre-handoff readiness check."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from export_pre_handoff_readiness import export_readiness
from pre_handoff_readiness import check_pre_handoff


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "pre_handoff_readiness.py",
    ROOT / "export_pre_handoff_readiness.py",
)
FOCUSED = ROOT / "test_pre_handoff_readiness.py"
FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "socket",
    "urllib",
    "boto3",
    "google",
    "azure",
    "celery",
    "apscheduler",
    "schedule",
}
PRIVATE_KEY_MARKERS = tuple(
    "-----BEGIN " + label + "-----"
    for label in (
        "PRIVATE" + " " + "KEY",
        "RSA" + " " + "PRIVATE" + " " + "KEY",
        "EC" + " " + "PRIVATE" + " " + "KEY",
        "OPENSSH" + " " + "PRIVATE" + " " + "KEY",
    )
)


def run() -> None:
    completed = subprocess.run(
        [sys.executable, str(FOCUSED)],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, f"focused pre-handoff suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[PreHandoff GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[PreHandoff GATE] no network/provider/scheduler imports: PASSED")

    readiness = check_pre_handoff(ROOT)
    assert readiness["decision"] == "INTERNAL_HANDOFF_READY"
    assert readiness["remediation_codes"] == []
    assert all(readiness["checks"].values())
    assert readiness["read_only"] is True
    assert readiness["external_submission_allowed"] is False
    assert readiness["authorization_promoted"] is False
    assert readiness["runtime_mutation_performed"] is False
    assert readiness["external_transmission_performed"] is False
    assert readiness["claim_boundary"]["production_ready"] is False
    assert readiness["claim_boundary"]["clinical_validation"] == "PENDING"
    assert readiness["external_gate_snapshot"] == {"blocked": 7, "evidence_submitted": 0, "open": 3, "passed": 0}
    print("[PreHandoff GATE] ready decision and locked claim/gate boundary: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "pre-handoff.json"
        exported = export_readiness(output=output, project_root=ROOT)
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved == exported
        assert exported["decision"] == "INTERNAL_HANDOFF_READY"
        assert exported["redaction_verified"] is True
    print("[PreHandoff GATE] redacted exporter round-trip: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"external_submission_allowed": False' in source
    assert '"authorization_promoted": False' in source
    assert '"runtime_mutation_performed": False' in source
    assert '"external_transmission_performed": False' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    serialized = json.dumps(readiness, ensure_ascii=True)
    for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@"):
        assert marker not in serialized
    print("[PreHandoff GATE] no-self-authorization, redaction and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[PreHandoff GATE] git diff --check: PASSED")
    print("PRE_HANDOFF_READINESS_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
