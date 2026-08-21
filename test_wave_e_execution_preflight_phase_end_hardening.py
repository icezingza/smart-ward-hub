from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys

from wave_e_execution_preflight import CRITERIA, build_empty_preflight


ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = ("test_wave_e_execution_preflight.py",)
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
        print(f"[Wave E PRECHECK GATE] {script}: PASSED")

    module_path = ROOT / "wave_e_execution_preflight.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[Wave E PRECHECK GATE] No endpoint/network/provider side effect: PASSED")

    preflight = build_empty_preflight(package_revision="wave-e-preflight-gate-20260821", source_revision="fixture-revision-gate")
    summary = preflight.validate_and_summarize()
    assert tuple(summary["missing_criteria"]) == CRITERIA
    assert summary["execution_permitted"] is False
    assert summary["external_validation_started"] is False
    assert summary["authorization_snapshot"] == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    print("[Wave E PRECHECK GATE] Entry criteria and authorization boundary lock: PASSED")

    gate_path = Path(__file__).resolve()
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == gate_path or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".env", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[Wave E PRECHECK GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Wave E PRECHECK GATE] git diff --check: PASSED")
    print("WAVE_E_EXECUTION_PREFLIGHT_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
