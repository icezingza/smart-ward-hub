"""Phase-end hardening gate for the P3 external-gate status reconciliation."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from export_p3_external_gate_status_reconciliation import export_external_gate_status
from p3_external_gate_status_reconciliation import reconcile_external_gates


ROOT = Path(__file__).resolve().parent
FOCUSED = ROOT / "test_p3_external_gate_status_reconciliation.py"
TARGETS = (
    ROOT / "p3_external_gate_status_reconciliation.py",
    ROOT / "export_p3_external_gate_status_reconciliation.py",
)
FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "socket",
    "urllib",
    "serial",
    "bleak",
    "paho",
    "websockets",
    "google",
    "azure",
    "boto3",
    "celery",
    "apscheduler",
    "schedule",
    "subprocess",
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
    env = os.environ.copy()
    env["PATH"] = f"{Path(sys.executable).parent}:{env.get('PATH', '')}"
    completed = subprocess.run(
        [sys.executable, str(FOCUSED)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, f"focused P3 gate suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[P3 Gates Gate] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[P3 Gates Gate] no network/provider/transport/scheduler imports: PASSED")

    report = reconcile_external_gates()
    assert report["decision"] == "P3_EXTERNAL_GATE_STATUS_RECONCILED"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["status_counts"] == {"BLOCKED": 7, "OPEN": 3, "EVIDENCE_SUBMITTED": 0, "TOTAL": 10}
    assert report["blocked_gate_ids"] == ["GV-01", "GV-03", "GV-04", "GV-06", "GV-07", "GV-08", "GV-09"]
    assert report["open_gate_ids"] == ["GV-02", "GV-05", "GV-10"]
    assert report["ready_for_external_review"] is False
    assert report["read_only"] is True
    assert report["external_transmission_performed"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["production_ready"] is False
    assert report["clinical_validation"] == "PENDING"
    assert report["hardware_evidence"] == "UNVERIFIED"
    print("[P3 Gates Gate] 10-gate status, blockers and locked boundary: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "external-gates.json"
        exported = export_external_gate_status(output=output)
        assert exported["decision"] == "P3_EXTERNAL_GATE_STATUS_RECONCILED"
        assert exported["redaction_verified"] is True
        assert exported["external_submission_allowed"] is False
        assert json.loads(output.read_text(encoding="utf-8")) == exported
    print("[P3 Gates Gate] exporter round-trip and redaction: PASSED")

    serialized = json.dumps(report, sort_keys=True, ensure_ascii=True).lower()
    for marker in ("hn-", "an-", "mrn", "patient_id", "patient_token", "private key", "bearer ", "password", "api_key", "@"):
        assert marker not in serialized
    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"ready_for_external_review": False' in source
    assert '"production_ready": False' in source
    assert '"external_submission_allowed": False' in source
    assert '"external_transmission_performed": False' in source
    assert '"runtime_mutation_performed": False' in source
    assert '"authorization_promoted": False' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    print("[P3 Gates Gate] redaction, no-self-authorization and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[P3 Gates Gate] git diff --check: PASSED")
    print("P3_EXTERNAL_GATE_STATUS_RECONCILIATION_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
