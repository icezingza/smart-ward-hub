from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from durable_worker_store import DurableWorkerPolicyError, DurableWorkerStore


ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = ("test_durable_worker_store.py",)
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
        print(f"[P2-005 DURABLE GATE] {script}: PASSED")

    tree = ast.parse((ROOT / "durable_worker_store.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[P2-005 DURABLE GATE] No network/subprocess/scheduler import: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        store = DurableWorkerStore(str(Path(directory) / "gate.db"), mode="software_fixture")
        health = store.health()
        assert health["journal_mode"] == "wal"
        assert health["synchronous"] == 2
        assert health["integrity_check"] == "ok"
        assert health["audit_chain_valid"] is True
        store.close()
    print("[P2-005 DURABLE GATE] SQLite WAL/FULL/integrity software fixture: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        try:
            DurableWorkerStore(str(Path(directory) / "production.db"), mode="production_durable")
        except DurableWorkerPolicyError:
            pass
        else:
            raise AssertionError("production durable mode must fail closed")
    print("[P2-005 DURABLE GATE] Unapproved production durable mode fails closed: PASSED")

    gate_path = Path(__file__).resolve()
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == gate_path or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".env", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[P2-005 DURABLE GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[P2-005 DURABLE GATE] git diff --check: PASSED")
    print("P2_005_DURABLE_WORKER_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
