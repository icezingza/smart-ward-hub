"""Phase-end hardening gate for the fixture-only replay harness."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from export_sync_alert_replay import export_evidence
from sync_alert_replay_harness import matrix_payload


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "sync_alert_replay_harness.py",
    ROOT / "export_sync_alert_replay.py",
)
FOCUSED = ROOT / "test_sync_alert_replay_harness.py"
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
    assert completed.returncode == 0, f"focused replay suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[Replay GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[Replay GATE] no network/provider/scheduler imports: PASSED")

    payload = matrix_payload()
    assert payload["contract"] == "SYNC_ALERT_REPLAY_HARNESS_V1"
    assert payload["mode"] == "FIXTURE_ONLY_SOFTWARE_SIMULATION"
    assert payload["read_only"] is True
    assert payload["execution_performed"] is False
    assert payload["external_transmission_performed"] is False
    assert payload["authorization_boundary"] == {
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
    }
    for row in payload["rows"]:
        assert row["mutation_performed"] is False
        assert row["purge_executed"] is False
        assert row["replay_executed"] is False
    print("[Replay GATE] fixture-only read-only decision contract: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "sync-alert-replay.json"
        evidence = export_evidence(output=output, project_root=ROOT)
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved == evidence
        assert evidence["transcript_integrity_valid"] is True
        assert evidence["redaction_verified"] is True
        assert evidence["read_only"] is True
        assert evidence["execution_performed"] is False
        assert evidence["external_transmission_performed"] is False
        assert len(evidence["transcript"]) == evidence["row_count"]
    print("[Replay GATE] redacted exporter and transcript hash-chain: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert "external_authority" in source and '"NONE"' in source
    assert "runtime_authority" in source and '"NONE"' in source
    assert '"execution_performed": False' in source
    assert '"external_transmission_performed": False' in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    serialized = json.dumps(evidence, ensure_ascii=True)
    for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@"):
        assert marker not in serialized
    print("[Replay GATE] no-self-authorization, redaction and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[Replay GATE] git diff --check: PASSED")
    print("SYNC_ALERT_REPLAY_HARNESS_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
