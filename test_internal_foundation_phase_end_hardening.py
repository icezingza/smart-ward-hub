from __future__ import annotations

import ast
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

from export_internal_foundation_readiness import export
from internal_foundation_readiness import AUTHORIZATION_BOUNDARY, evaluate_internal_foundation
from test_internal_foundation_readiness import valid_environment


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "internal_foundation_readiness.py",
    ROOT / "edge_runtime.py",
    ROOT / "schemas.py",
    ROOT / "export_internal_foundation_readiness.py",
)
FOCUSED_TESTS = ("test_internal_foundation_readiness.py", "test_edge_runtime.py")
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
FORBIDDEN_AUTHORIZATION_STATES = {
    "AUTHORIZED_BY_EXTERNAL_OWNER",
    "READY_FOR_EXTERNAL_EXECUTION",
    "PRODUCTION_AUTHORIZED",
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
    env = {"PATH": f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}"}
    for script in FOCUSED_TESTS:
        completed = subprocess.run(
            [sys.executable, str(ROOT / script)],
            cwd=ROOT,
            env={**os.environ, **env},
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, f"{script} failed:\n{completed.stdout}\n{completed.stderr}"
        print(f"[Foundation GATE] {script}: PASSED")

    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert not imported.intersection(FORBIDDEN_IMPORTS), (target, imported.intersection(FORBIDDEN_IMPORTS))
    print("[Foundation GATE] No network/provider/scheduler side effect: PASSED")

    result = evaluate_internal_foundation(valid_environment(ROOT), project_root=ROOT)
    assert result["status"] == "PASS", result
    assert result["software_only"] is True
    assert result["physical_validation"] == "UNVERIFIED"
    assert result["clinical_validation"] == "PENDING"
    assert result["authorization_boundary"] == AUTHORIZATION_BOUNDARY
    assert result["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    print("[Foundation GATE] Runtime readiness and external-boundary lock: PASSED")

    original_environment = os.environ.copy()
    try:
        os.environ.update(valid_environment(ROOT))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "foundation.json"
            exported = export(output, project_root=ROOT)
            assert json.loads(output.read_text(encoding="utf-8")) == exported
            assert exported["snapshot_kind"] == "INTERNAL_FOUNDATION_READINESS"
            assert exported["evidence_class"] == "LOCAL_SOFTWARE_SIMULATION"
            assert exported["status"] == "PASS"
            assert exported["authorization_boundary"] == AUTHORIZATION_BOUNDARY
    finally:
        os.environ.clear()
        os.environ.update(original_environment)
    print("[Foundation GATE] Exported redacted readiness snapshot: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert not any(state in source for state in FORBIDDEN_AUTHORIZATION_STATES)
    print("[Foundation GATE] No-self-authorization claim lock: PASSED")

    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or path.resolve() == Path(__file__).resolve()
            or ".git" in path.parts
            or ".venv" in path.parts
        ):
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".env", ".example", ".ini", ".sh"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[Foundation GATE] Private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Foundation GATE] git diff --check: PASSED")
    print("INTERNAL_FOUNDATION_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
