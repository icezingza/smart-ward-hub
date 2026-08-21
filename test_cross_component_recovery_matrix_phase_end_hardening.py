from __future__ import annotations

import ast
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from cross_component_recovery_matrix import run_matrix


ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "cross_component_recovery_matrix.py"
FOCUSED = ROOT / "test_cross_component_recovery_matrix.py"
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
    assert completed.returncode == 0, f"focused recovery matrix test failed:\n{completed.stdout}\n{completed.stderr}"
    print("[Recovery Matrix GATE] focused/adversarial suite: PASSED")

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
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

    source = TARGET.read_text(encoding="utf-8")
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert "resume_permitted_after_unresolved_fault\": False" in source
    print("[Recovery Matrix GATE] no-self-authorization and no-resume claim lock: PASSED")

    for path in (TARGET, FOCUSED, Path(__file__)):
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[Recovery Matrix GATE] private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Recovery Matrix GATE] git diff --check: PASSED")
    print("CROSS_COMPONENT_RECOVERY_MATRIX_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
