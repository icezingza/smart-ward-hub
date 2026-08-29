from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys

from serial_bench_evidence_contract import validate_bench_evidence
from serial_bench_runner import BenchConfig, run as run_bench


ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = ("test_serial_bench_runner.py", "test_serial_bench_evidence_contract.py")
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
        print(f"[P2-002 GATE] {script}: PASSED")

    dry = run_bench(
        BenchConfig(
            port=None,
            baudrate=115200,
            timeout_seconds=1.0,
            max_payload=4096,
            output=ROOT / "serial_bench_evidence.json",
            dry_run=True,
            confirm_physical=None,
        )
    )
    assert dry["status"] == "DRY_RUN_ONLY"
    assert dry["physical_hardware_validation"] == "PENDING"
    assert dry["physical_confirmation_verified"] is False
    assert validate_bench_evidence(dry)["valid"] is True
    print("[P2-002 GATE] Dry-run cannot assert physical hardware or production network: PASSED")

    tree = ast.parse((ROOT / "serial_bench_runner.py").read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"system", "popen"}
        for node in ast.walk(tree)
    )
    print("[P2-002 GATE] Runner has no shell execution path: PASSED")

    gate_path = Path(__file__).resolve()
    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or path.resolve() == gate_path
            or ".git" in path.parts
            or ".venv" in path.parts
        ):
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".env", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[P2-002 GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[P2-002 GATE] git diff --check: PASSED")
    print("P2_002_SERIAL_EVIDENCE_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
