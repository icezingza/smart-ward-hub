from __future__ import annotations

import ast
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from evidence_reconciliation import BOUNDARY, EXPECTED_EXTERNAL_GATE_SNAPSHOT, default_paths, reconcile_packages


ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = ("test_evidence_reconciliation.py",)
FORBIDDEN_IMPORTS = {"requests", "httpx", "socket", "subprocess", "urllib", "boto3", "google", "azure", "celery", "apscheduler", "schedule"}
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
        print(f"[Reconciliation GATE] {script}: PASSED")

    tree = ast.parse((ROOT / "evidence_reconciliation.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[Reconciliation GATE] No endpoint/network/provider side effect: PASSED")

    freeze_path = default_paths(ROOT)["freeze_path"]
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    frozen_revision = freeze["source_revision"]
    with tempfile.TemporaryDirectory() as directory:
        frozen_root = Path(directory)
        archive = subprocess.run(["git", "archive", frozen_revision], cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            tar.extractall(frozen_root, filter="data")
        (frozen_root / freeze_path.relative_to(ROOT)).write_bytes(freeze_path.read_bytes())
        result = reconcile_packages(**default_paths(frozen_root))
    assert result["gate_decision"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert result["execution_permitted"] is False
    assert result["submission_permitted"] is False
    assert result["authorization_boundary"] == BOUNDARY
    assert result["external_gate_snapshot"] == EXPECTED_EXTERNAL_GATE_SNAPSHOT
    assert result["package_checks"] == {
        "release_freeze": "PASS",
        "wave4": "PASS",
        "reviewer_preflight": "PASS",
        "wave_e_preflight": "PASS",
        "wave0_template": "PASS",
    }
    assert result["states"]["wave_e_execution_permitted"] is False
    assert result["states"]["wave_e_external_validation_started"] is False
    live_result = reconcile_packages(**default_paths(ROOT))
    assert live_result["source_revision_alignment"] == "ANCESTOR_VERIFIED_REQUIRES_REGENERATION"
    for package in ("wave4", "reviewer", "wave_e"):
        assert live_result["source_revision_lineage"][package]["ancestor_verified"] is True
        assert live_result["source_revision_lineage"][package]["relation"] == "ANCESTOR_REQUIRES_REGENERATION"
    assert live_result["source_revision_lineage"]["wave0"]["ancestor_verified"] is False
    assert live_result["source_revision_lineage"]["wave0"]["relation"] == "NON_ANCESTOR_BLOCKED"
    assert live_result["execution_permitted"] is False
    assert live_result["submission_permitted"] is False
    print("[Reconciliation GATE] Cross-package checks, live Git ancestry and no-authorization decision lock: PASSED")

    gate_path = Path(__file__).resolve()
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == gate_path or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".env", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[Reconciliation GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Reconciliation GATE] git diff --check: PASSED")
    print("EVIDENCE_RECONCILIATION_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
