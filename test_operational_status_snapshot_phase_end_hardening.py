from __future__ import annotations

import ast
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

from operational_status_snapshot import collect_operational_snapshot
from test_internal_foundation_readiness import valid_environment


ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "operational_status_snapshot.py"
FOCUSED = ROOT / "test_operational_status_snapshot.py"
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
    assert completed.returncode == 0, f"focused operational snapshot test failed:\n{completed.stdout}\n{completed.stderr}"
    print("[Operational GATE] focused/adversarial snapshot suite: PASSED")

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)

    git_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                git_calls.append(node)
    assert len(git_calls) == 1
    command = git_calls[0].args[0]
    assert isinstance(command, ast.List)
    assert [item.value for item in command.elts if isinstance(item, ast.Constant)] == ["git", "-C", "rev-parse", "HEAD"]
    print("[Operational GATE] no network/provider side effect and fixed local git read: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        runtime_root = Path(directory)
        env = valid_environment(ROOT)
        env.update(
            {
                "SW_DATABASE_PATH": str(runtime_root / "ward_hub.db"),
                "SW_TELEMETRY_STATE_PATH": str(runtime_root / "state.json"),
                "SW_AUDIT_LOG_PATH": str(runtime_root / "audit.jsonl"),
            }
        )
        first = collect_operational_snapshot(env, project_root=ROOT, now=2_000_000_000)
        second = collect_operational_snapshot(env, project_root=ROOT, now=2_000_000_000)
        assert first == second
        assert first["authorization_boundary"]["external_authority"] == "NONE"
        assert first["authorization_boundary"]["clinical_validation_authorized"] is False
        assert first["authorization_boundary"]["production_authorized"] is False
        serialized = json.dumps(first, ensure_ascii=True)
        assert "SW_AUTH_TOKENS_JSON" not in serialized
        assert "patient_token" not in serialized
        assert "patient_id" not in serialized
    print("[Operational GATE] deterministic redacted snapshot and authorization lock: PASSED")

    for path in (TARGET, FOCUSED, Path(__file__)):
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[Operational GATE] private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Operational GATE] git diff --check: PASSED")
    print("OPERATIONAL_STATUS_SNAPSHOT_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
