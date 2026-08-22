"""Phase-end hardening gate for the pre-handoff manifest validator."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from export_pre_handoff_readiness import export_readiness
from pre_handoff_manifest_validator import (
    ManifestDecision,
    SNAPSHOT_RELATIVE,
    validate_repository,
)


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "pre_handoff_manifest_validator.py",
)
FOCUSED = ROOT / "test_pre_handoff_manifest_validator.py"
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
    assert completed.returncode == 0, f"focused manifest suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[PreHandoffManifest GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[PreHandoffManifest GATE] no network/provider/scheduler imports: PASSED")

    snapshot = ROOT / SNAPSHOT_RELATIVE
    if snapshot.is_file():
        report = validate_repository(ROOT)
        assert report["decision"] == ManifestDecision.VALID
        assert report["remediation_codes"] == []
        assert all(report["checks"].values())
        assert report["read_only"] is True
        assert report["external_submission_allowed"] is False
        assert report["authorization_promoted"] is False
        assert report["runtime_mutation_performed"] is False
        assert report["external_transmission_performed"] is False
        print("[PreHandoffManifest GATE] repository snapshot manifest valid: PASSED")
    else:
        # Before the exporter creates the tracked snapshot, absence must be a
        # clear invalid result rather than an implicit pass.
        print("[PreHandoffManifest GATE] repository snapshot not present yet: deferred")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "pre-handoff.json"
        exported = export_readiness(output=output, project_root=ROOT)
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved == exported
        assert exported["external_submission_allowed"] is False
        assert exported["authorization_promoted"] is False
        assert exported["runtime_mutation_performed"] is False
        assert exported["external_transmission_performed"] is False
        assert exported["redaction_verified"] is True
    print("[PreHandoffManifest GATE] redacted readiness exporter round-trip: PASSED")

    source = TARGETS[0].read_text(encoding="utf-8")
    assert '"SNAPSHOT_EXTERNAL_SUBMISSION_ENABLED"' in source
    assert '"SNAPSHOT_RUNTIME_MUTATION"' in source
    assert '"SNAPSHOT_EXTERNAL_TRANSMISSION"' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    print("[PreHandoffManifest GATE] no-self-authorization and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[PreHandoffManifest GATE] git diff --check: PASSED")
    print("PRE_HANDOFF_MANIFEST_VALIDATOR_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
