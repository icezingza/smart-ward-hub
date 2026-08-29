from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile

from export_external_decision_lifecycle import export
import sys

from external_decision_lifecycle import (
    AUTHORIZATION_BOUNDARY,
    DecisionLifecycle,
    PENDING_EXTERNAL_VERIFICATION,
    TRANSITIONS,
)
from test_external_decision_record import received_record


ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = ("test_external_decision_lifecycle.py",)
TARGETS = (
    ROOT / "external_decision_lifecycle.py",
    ROOT / "export_external_decision_lifecycle.py",
)
FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "socket",
    "subprocess",
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
FORBIDDEN_AUTHORIZATION_STATES = {
    "AUTHORIZED_BY_EXTERNAL_OWNER",
    "READY_FOR_EXTERNAL_EXECUTION",
    "PRODUCTION_AUTHORIZED",
}


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
        print(f"[Lifecycle GATE] {script}: PASSED")

    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert not imported.intersection(FORBIDDEN_IMPORTS), (target, imported.intersection(FORBIDDEN_IMPORTS))
    print("[Lifecycle GATE] No network/provider/scheduler side effect: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"authorization_promoted": False' in source
    assert '"authorization_promoted": True' not in source
    assert '"external_decision_verified": True' not in source
    assert '"external_execution_authorized": True' not in source
    assert '"production_authorized": True' not in source
    assert FORBIDDEN_AUTHORIZATION_STATES.isdisjoint(set(TRANSITIONS) | {target for targets in TRANSITIONS.values() for target in targets})
    print("[Lifecycle GATE] No-self-authorization boundary and state lock: PASSED")

    fixture_now = datetime(2026, 8, 21, 10, 30, tzinfo=timezone.utc)
    lifecycle = DecisionLifecycle(received_record(), now=fixture_now)
    status = lifecycle.status(now=fixture_now)
    assert status["state"] == PENDING_EXTERNAL_VERIFICATION
    assert status["trusted"] is False
    assert status["external_decision_verified"] is False
    assert status["authorization_promoted"] is False
    assert status["external_execution_authorized"] is False
    assert status["production_authorized"] is False
    assert status["clinical_validation_authorized"] is False
    assert status["authorization_boundary"] == AUTHORIZATION_BOUNDARY
    assert lifecycle.audit_chain_valid() is True
    snapshot = lifecycle.snapshot()
    assert snapshot["authorization_boundary"] == AUTHORIZATION_BOUNDARY
    assert all(event["schema_version"] == "external-decision-lifecycle-v1" for event in snapshot["events"])
    print("[Lifecycle GATE] Runtime authorization flags, schema, and audit chain: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "external-decision-lifecycle.json"
        exported = export(output)
        written = json.loads(output.read_text(encoding="utf-8"))
        assert written == exported
        assert exported["snapshot_kind"] == "EXTERNAL_DECISION_LIFECYCLE_TEMPLATE"
        assert exported["lifecycle_instantiated"] is False
        assert exported["authorization_promoted"] is False
        assert exported["external_decision_verified"] is False
        assert exported["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    print("[Lifecycle GATE] Deterministic blank-safe exporter snapshot: PASSED")

    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or path.resolve() == Path(__file__).resolve()
            or ".git" in path.parts
            or ".venv" in path.parts
        ):
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".env", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[Lifecycle GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Lifecycle GATE] git diff --check: PASSED")
    print("EXTERNAL_DECISION_LIFECYCLE_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
