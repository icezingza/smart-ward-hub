"""Phase-end hardening gate for cross-package evidence binding."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from cross_package_evidence_binding import check_repository
from export_cross_package_evidence_binding import export_evidence


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "cross_package_evidence_binding.py",
    ROOT / "export_cross_package_evidence_binding.py",
)
FOCUSED = ROOT / "test_cross_package_evidence_binding.py"
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
    assert completed.returncode == 0, f"focused binding suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[CrossPackage GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[CrossPackage GATE] no network/provider/scheduler imports: PASSED")

    report = check_repository(ROOT)
    assert report["decision"] == "BOUND"
    assert report["remediation_codes"] == ["EVIDENCE_PACKAGES_BOUND"]
    assert report["read_only"] is True
    assert report["external_transmission_performed"] is False
    assert all(report["checks"].values())
    assert report["authorization_boundary"] == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    print("[CrossPackage GATE] repository binding and locked boundary: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "cross-package-binding.json"
        evidence = export_evidence(output=output, project_root=ROOT)
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved == evidence
        assert evidence["decision"] == "BOUND"
        assert evidence["redaction_verified"] is True
        assert evidence["read_only"] is True
        assert evidence["external_transmission_performed"] is False
    print("[CrossPackage GATE] redacted exporter round-trip: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"external_transmission_performed": False' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert '"runtime_authority": "WORKER"' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    serialized = json.dumps(evidence, ensure_ascii=True)
    for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@"):
        assert marker not in serialized
    print("[CrossPackage GATE] no-self-authorization, redaction and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[CrossPackage GATE] git diff --check: PASSED")
    print("CROSS_PACKAGE_EVIDENCE_BINDING_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
