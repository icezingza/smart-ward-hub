from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys

from worker_control_plane import WorkerControlPlane


ROOT = Path(__file__).resolve().parent
WORKER_SOURCE = ROOT / "worker_control_plane.py"
FOCUSED_TESTS = ("test_worker_control_plane.py",)
FORBIDDEN_IMPORTS = {"requests", "httpx", "socket", "subprocess", "celery", "apscheduler", "schedule"}
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
    for script in FOCUSED_TESTS:
        completed = subprocess.run(
            [sys.executable, str(ROOT / script)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, f"{script} failed:\n{completed.stdout}\n{completed.stderr}"
        print(f"[P2-005 GATE] {script}: PASSED")

    tree = ast.parse(WORKER_SOURCE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"start", "create_task"} for node in ast.walk(tree))
    print("[P2-005 GATE] No scheduler/network/subprocess side effect in control plane: PASSED")

    plane = WorkerControlPlane(handlers={"backup.report": lambda args: {"ok": True}})
    job = plane.submit(
        job_id="gate-job-001",
        job_type="BACKUP_REPORT",
        args={"report_kind": "gate"},
        idempotency_key="gate-idem-001",
        requester_role="reliability_operator",
        approver_role="security_auditor",
        approval_ref="gate-approval-001",
    )
    assert job["status"] == "QUEUED"
    assert plane.verify_audit_chain() is True
    print("[P2-005 GATE] Non-clinical approval and audit boundary: PASSED")

    gate_path = Path(__file__).resolve()
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == gate_path or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".env", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[P2-005 GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[P2-005 GATE] git diff --check: PASSED")
    print("P2_005_WORKER_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
