from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from power_loss_recovery_harness import run_harness


ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = (
    "test_edge_runtime.py",
    "test_p0_recovery.py",
    "test_power_loss_recovery_harness.py",
)
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
        print(f"[P0-004 GATE] {script}: PASSED")

    report = run_harness()
    assert report["all_passed"] is True
    assert report["checkpoint_invariant_hardening"] == "SOFTWARE_VERIFIED"
    assert report["physical_power_cut"] == "UNVERIFIED"
    assert report["disk_full_drill"] == "UNVERIFIED"
    assert report["filesystem_corruption_drill"] == "SOFTWARE_CORRUPTION_ONLY"
    required_scenarios = {
        "pii_checkpoint_rejected",
        "sequence_inconsistency_rejected",
        "last_sequence_mismatch_rejected",
    }
    assert required_scenarios.issubset({item["scenario"] for item in report["results"]})
    print("[P0-004 GATE] Recovery invariant evidence contract: PASSED")

    evidence = json.loads((ROOT / "P0_POWER_LOSS_SOFTWARE_EVIDENCE.json").read_text(encoding="utf-8"))
    assert evidence["all_passed"] is True
    assert evidence["checkpoint_invariant_hardening"] == "SOFTWARE_VERIFIED"
    assert evidence["patient_data_used"] is False
    print("[P0-004 GATE] Machine-readable evidence binding: PASSED")

    gate_path = Path(__file__).resolve()
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == gate_path or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".env", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[P0-004 GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[P0-004 GATE] git diff --check: PASSED")
    print("P0_004_RECOVERY_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
