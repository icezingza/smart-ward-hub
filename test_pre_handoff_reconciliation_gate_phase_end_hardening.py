"""Phase-end hardening gate for the aggregate pre-handoff reconciliation gate."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from export_pre_handoff_reconciliation_gate import export_reconciliation
from pre_handoff_reconciliation_gate import check_repository


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "pre_handoff_reconciliation_gate.py",
    ROOT / "export_pre_handoff_reconciliation_gate.py",
)
FOCUSED = ROOT / "test_pre_handoff_reconciliation_gate.py"
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
    assert completed.returncode == 0, f"focused reconciliation suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[Reconciliation GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[Reconciliation GATE] no network/provider/scheduler imports: PASSED")

    report = check_repository(ROOT)
    assert report["decision"] == "INTERNAL_HANDOFF_RECONCILIATION_READY"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["child_decisions"] == {
        "drift": "DRIFT_FREE",
        "manifest": "MANIFEST_VALID",
        "selection": "SELECTED_SET_VALID",
        "consistency": "SELECTION_MANIFEST_CONSISTENT",
    }
    assert report["selected_count"] == 12
    assert report["read_only"] is True
    assert report["external_submission_allowed"] is False
    assert report["authorization_promoted"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["external_transmission_performed"] is False
    print("[Reconciliation GATE] aggregate child gates and locked output: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "report.json"
        target.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
        before = target.read_bytes()
        _ = check_repository(ROOT)
        assert target.read_bytes() == before
        exported_path = Path(directory) / "aggregate.json"
        exported = export_reconciliation(output=exported_path, project_root=ROOT)
        assert exported["decision"] == "INTERNAL_HANDOFF_RECONCILIATION_READY"
        assert exported["redaction_verified"] is True
        assert exported["read_only"] is True
        assert exported["external_submission_allowed"] is False
        assert exported["authorization_promoted"] is False
        assert json.loads(exported_path.read_text(encoding="utf-8")) == exported
    print("[Reconciliation GATE] read-only filesystem and exporter round trip: PASSED")

    serialized = json.dumps(report, sort_keys=True, ensure_ascii=True)
    for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@"):
        assert marker not in serialized
    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"external_submission_allowed": False' in source
    assert '"authorization_promoted": False' in source
    assert '"runtime_mutation_performed": False' in source
    assert '"external_transmission_performed": False' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    print("[Reconciliation GATE] redaction, no-self-authorization and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Reconciliation GATE] git diff --check: PASSED")
    print("PRE_HANDOFF_RECONCILIATION_GATE_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
