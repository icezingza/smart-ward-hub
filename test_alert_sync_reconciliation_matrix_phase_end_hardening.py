"""Phase-end hardening gate for the alert/sync reconciliation workstream."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from alert_sync_reconciliation_matrix import matrix_payload
from export_alert_sync_reconciliation import export_evidence


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "alert_sync_reconciliation_matrix.py",
    ROOT / "export_alert_sync_reconciliation.py",
)
FOCUSED = ROOT / "test_alert_sync_reconciliation_matrix.py"
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
    assert completed.returncode == 0, f"focused suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[AlertSync GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[AlertSync GATE] no network/provider/scheduler imports: PASSED")

    payload = matrix_payload()
    assert payload["contract"] == "ALERT_SYNC_RECONCILIATION_MATRIX_V1"
    assert payload["mode"] == "SOFTWARE_SIMULATION_ONLY"
    assert payload["authorization_boundary"] == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
    }
    assert all(
        set((row["resume_permitted"], row["recovery_decision"], row["remediation_code"]))
        for row in payload["rows"]
    )
    print("[AlertSync GATE] decision contract and authorization boundary: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "alert-sync-reconciliation.json"
        evidence = export_evidence(output=output, project_root=ROOT)
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved == evidence
        assert evidence["read_only"] is True
        assert evidence["execution_performed"] is False
        assert evidence["software_simulation_only"] is True
        assert evidence["transcript_integrity_valid"] is True
        assert evidence["redaction_verified"] is True
        assert len(evidence["transcript"]) == evidence["matrix_row_count"]
    print("[AlertSync GATE] redacted exporter and transcript hash-chain: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert '"external_authority": "NONE"' in source
    assert '"runtime_authority": "NONE"' in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    serialized = json.dumps(evidence, ensure_ascii=True)
    for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@"):
        assert marker not in serialized
    print("[AlertSync GATE] no-self-authorization, redaction and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[AlertSync GATE] git diff --check: PASSED")
    print("ALERT_SYNC_RECONCILIATION_MATRIX_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
