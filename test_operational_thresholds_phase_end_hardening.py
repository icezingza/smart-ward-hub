from __future__ import annotations

import ast
from pathlib import Path
import os
import subprocess
import sys

from operational_thresholds import DEFAULT_THRESHOLDS, evaluate_thresholds, load_thresholds


ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "operational_thresholds.py"
FOCUSED = ROOT / "test_operational_thresholds.py"
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
    assert completed.returncode == 0, f"threshold focused test failed:\n{completed.stdout}\n{completed.stderr}"
    print("[Threshold GATE] focused/adversarial suite: PASSED")

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[Threshold GATE] no network/provider/scheduler side effect: PASSED")

    healthy = {
        "preflight_status": "PASS",
        "runtime": {
            "database": {"status": "PASS"},
            "checkpoint": {"status": "PRESENT", "age_seconds": 1},
            "backup": {"status": "PRESENT", "age_seconds": 1},
            "audit": {"status": "PRESENT", "age_seconds": 1},
            "anchor": {"status": "PRESENT", "age_seconds": 1},
            "disk": {"status": "PASS", "free_ratio": 0.90},
        },
    }
    report = evaluate_thresholds(healthy, metrics={"sync_backlog": 0, "worker_queue_backlog": 0, "unresolved_alerts": 0})
    assert report["status"] == "PASS"
    assert report["resume_permitted"] is True
    assert report["thresholds"] == DEFAULT_THRESHOLDS

    blocked = evaluate_thresholds(healthy, metrics={"sync_backlog": 1, "worker_queue_backlog": 1, "unresolved_alerts": 1})
    assert blocked["status"] == "BLOCKED_REQUIRES_RECONCILIATION"
    assert blocked["resume_permitted"] is False
    assert len(blocked["remediation_codes"]) == 3
    print("[Threshold GATE] healthy/blocked resume boundary and remediation output: PASSED")

    source = TARGET.read_text(encoding="utf-8")
    assert '"resume_permitted": not remediation_codes' in source
    assert "BLOCKED_REQUIRES_RECONCILIATION" in source
    assert "production_authorized" not in source
    assert "clinical_validation_authorized" not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    print("[Threshold GATE] no authorization mutation and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Threshold GATE] git diff --check: PASSED")
    print("OPERATIONAL_THRESHOLDS_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
