from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys

from external_decision_record import AUTHORIZATION_BOUNDARY, template, validate


ROOT = Path(__file__).resolve().parent
FORBIDDEN_IMPORTS = {"requests", "httpx", "socket", "urllib", "boto3", "google", "azure", "celery", "apscheduler", "schedule"}
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
    focused = subprocess.run(
        [sys.executable, str(ROOT / "test_external_decision_record.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert focused.returncode == 0, f"focused test failed:\n{focused.stdout}\n{focused.stderr}"
    print("[Decision Record GATE] focused/adversarial tests: PASSED")

    tree = ast.parse((ROOT / "external_decision_record.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[Decision Record GATE] no network/provider side effect: PASSED")

    payload = template()
    result = validate(payload, template_only=True)
    assert result["decision_record_ready"] is False
    assert result["authorization_promoted"] is False
    assert result["external_decision_verified"] is False
    assert payload["authorization_boundary"] == AUTHORIZATION_BOUNDARY
    assert payload["production_authorized"] is False
    assert payload["clinical_validation_authorized"] is False
    print("[Decision Record GATE] blank-safe template and no-authorization lock: PASSED")

    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or ".git" in path.parts
            or ".venv" in path.parts
            or path.name == Path(__file__).name
        ):
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".env", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(marker in text for marker in PRIVATE_KEY_MARKERS), f"private-key marker found in {path}"
    print("[Decision Record GATE] private-key block scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Decision Record GATE] git diff --check: PASSED")
    print("EXTERNAL_DECISION_RECORD_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
