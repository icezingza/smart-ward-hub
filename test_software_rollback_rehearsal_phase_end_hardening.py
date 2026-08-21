from __future__ import annotations

import ast
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

from software_rollback_rehearsal import run_rehearsal


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "software_rollback_rehearsal.py",
    ROOT / "backup_restore.py",
    ROOT / "worker_queue_backup.py",
)
FOCUSED = (
    ROOT / "test_software_rollback_rehearsal.py",
    ROOT / "test_backup_restore.py",
    ROOT / "test_worker_queue_backup.py",
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
        assert completed.returncode == 0, f"rollback focused test failed ({focused.name}):\n{completed.stdout}\n{completed.stderr}"
    print("[Rollback GATE] focused/adversarial restore suites: PASSED")

    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert not imported.intersection(FORBIDDEN_IMPORTS), (target, imported.intersection(FORBIDDEN_IMPORTS))
    print("[Rollback GATE] no network/provider imports: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "rollback.json"
        report = run_rehearsal(output)
        assert json.loads(output.read_text(encoding="utf-8")) == report
        assert report["checks"]["all_post_restore_checks_passed"] is True
        assert report["checks"]["resume_permitted_in_software_rehearsal"] is True
        assert report["checks"]["production_resume_permitted"] is False
        assert report["checks"]["external_resume_permitted"] is False
        assert report["physical_power_cut"] == "UNVERIFIED"
        assert report["target_host_validation"] == "UNVERIFIED"
        serialized = json.dumps(report, ensure_ascii=True)
        assert "patient_token" not in serialized
        assert "patient_id" not in serialized
        assert "PRIVATE KEY" not in serialized
    print("[Rollback GATE] isolated artifacts, redaction and resume boundaries: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert '"external_authority": "NONE"' in source
    assert 'checks["production_resume_permitted"] = False' in source
    assert 'checks["external_resume_permitted"] = False' in source
    print("[Rollback GATE] no-self-authorization and no-production-resume lock: PASSED")

    for path in (*TARGETS, *FOCUSED, Path(__file__)):
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[Rollback GATE] private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Rollback GATE] git diff --check: PASSED")
    print("SOFTWARE_ROLLBACK_REHEARSAL_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
