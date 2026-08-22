"""Phase-end hardening gate for repository visibility governance."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from export_repository_visibility_governance import export_visibility
from repository_visibility_governance import check_repository


ROOT = Path(__file__).resolve().parent
FOCUSED = ROOT / "test_repository_visibility_governance.py"
TARGETS = (
    ROOT / "repository_visibility_governance.py",
    ROOT / "export_repository_visibility_governance.py",
)
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
    "subprocess",
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
    env = os.environ.copy()
    env["PATH"] = f"{Path(sys.executable).parent}:{env.get('PATH', '')}"
    completed = subprocess.run(
        [sys.executable, str(FOCUSED)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, f"focused visibility suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[Visibility GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[Visibility GATE] no network/provider/scheduler/subprocess imports: PASSED")

    report = check_repository(ROOT)
    assert report["decision"] == "REPOSITORY_VISIBILITY_BLOCKED"
    assert "REPOSITORY_NOT_PRIVATE" in report["remediation_codes"]
    assert report["repository"] == "icezingza/smart-ward-hub"
    assert report["is_private"] is False
    assert report["default_branch"] == "main"
    assert report["read_only"] is True
    assert report["external_submission_allowed"] is False
    assert report["authorization_promoted"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["external_transmission_performed"] is False
    print("[Visibility GATE] live observation is fail-closed and read-only: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "visibility.json"
        exported = export_visibility(output=output, project_root=ROOT)
        assert exported["decision"] == "REPOSITORY_VISIBILITY_BLOCKED"
        assert exported["redaction_verified"] is True
        assert json.loads(output.read_text(encoding="utf-8")) == exported
    print("[Visibility GATE] exporter round trip and redaction: PASSED")

    serialized = json.dumps(report, sort_keys=True, ensure_ascii=True)
    for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@"):
        assert marker not in serialized
    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"external_submission_allowed": False' in source
    assert '"authorization_promoted": False' in source
    assert '"runtime_mutation_performed": False' in source
    assert '"external_transmission_performed": False' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    print("[Visibility GATE] redaction, no-self-authorization and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Visibility GATE] git diff --check: PASSED")
    print("REPOSITORY_VISIBILITY_GOVERNANCE_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
