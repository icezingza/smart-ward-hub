from __future__ import annotations

import ast
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from cross_component_recovery_matrix import run_matrix


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "cross_component_recovery_matrix.py",
    ROOT / "durable_worker_store.py",
    ROOT / "edge_runtime.py",
    ROOT / "worker_queue_backup.py",
)
FOCUSED = (
    ROOT / "test_cross_component_recovery_matrix.py",
    ROOT / "test_durable_worker_store.py",
    ROOT / "test_edge_runtime.py",
)
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
    for focused in FOCUSED:
        completed = subprocess.run(
            [sys.executable, str(focused)],
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, f"focused recovery test failed ({focused.name}):\n{completed.stdout}\n{completed.stderr}"
    print("[Recovery Matrix GATE] focused/adversarial recovery suites: PASSED")

    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert not imported.intersection(FORBIDDEN_IMPORTS), (target, imported.intersection(FORBIDDEN_IMPORTS))
    print("[Recovery Matrix GATE] no network/provider/scheduler side effect: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "matrix.json"
        report = run_matrix(output)
        assert report["all_passed"] is True
        assert report["normal_resume_after_verified_roundtrip"] is True
        assert report["resume_permitted_after_unresolved_fault"] is False
        assert report["recovery_decision_on_unverified_component"] == "RECONCILIATION_REQUIRED"
        assert report["external_authority"] == "NONE"
        assert report["clinical_validation_authorized"] is False
        assert report["production_authorized"] is False
        assert output.is_file()
    print("[Recovery Matrix GATE] normal-resume and unresolved-fault stop boundary: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert "resume_permitted_after_unresolved_fault\": False" in source
    print("[Recovery Matrix GATE] no-self-authorization and no-resume claim lock: PASSED")

    for path in (*TARGETS, *FOCUSED, Path(__file__)):
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[Recovery Matrix GATE] private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Recovery Matrix GATE] git diff --check: PASSED")
    print("CROSS_COMPONENT_RECOVERY_MATRIX_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
