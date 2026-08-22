"""Phase-end hardening gate for the P2-002 transport selection control."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from export_p2_002_transport_selection import export_transport_selection
from p2_002_transport_selection import evaluate_transport_selection


ROOT = Path(__file__).resolve().parent
FOCUSED = ROOT / "test_p2_002_transport_selection.py"
TARGETS = (
    ROOT / "p2_002_transport_selection.py",
    ROOT / "export_p2_002_transport_selection.py",
)
FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "socket",
    "urllib",
    "serial",
    "bleak",
    "paho",
    "websockets",
    "google",
    "azure",
    "boto3",
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
    assert completed.returncode == 0, f"focused P2-002 selection suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[P2-002 Selection Gate] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[P2-002 Selection Gate] no network/provider/transport/scheduler imports: PASSED")

    report = evaluate_transport_selection()
    assert report["decision"] == "P2_002_TRANSPORT_SELECTION_VERIFIED"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["selected_software_transport"] == "serial"
    assert report["physical_gate_status"] == "NOT_STARTED"
    assert report["hardware_evidence"] == "UNVERIFIED"
    assert report["read_only"] is True
    assert report["fixture_only"] is True
    assert report["external_submission_allowed"] is False
    assert report["external_transmission_performed"] is False
    assert report["runtime_mutation_performed"] is False
    assert report["authorization_promoted"] is False
    assert report["production_ready"] is False
    print("[P2-002 Selection Gate] selected software profile and locked physical boundary: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "transport-selection.json"
        exported = export_transport_selection(output=output)
        assert exported["decision"] == "P2_002_TRANSPORT_SELECTION_VERIFIED"
        assert exported["redaction_verified"] is True
        assert exported["freeze_binding_required"] is True
        assert json.loads(output.read_text(encoding="utf-8")) == exported
    print("[P2-002 Selection Gate] exporter round-trip and redaction: PASSED")

    serialized = json.dumps(report, sort_keys=True, ensure_ascii=True).lower()
    for marker in ("hn-", "an-", "mrn", "patient_id", "patient_token", "private key", "bearer ", "password", "api_key", "@"):
        assert marker not in serialized
    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"selected_software_transport": SELECTED_SOFTWARE_TRANSPORT' in source
    assert '"production_ready": False' in source
    assert '"external_submission_allowed": False' in source
    assert '"external_transmission_performed": False' in source
    assert '"runtime_mutation_performed": False' in source
    assert '"authorization_promoted": False' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    print("[P2-002 Selection Gate] redaction, no-self-authorization and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[P2-002 Selection Gate] git diff --check: PASSED")
    print("P2_002_TRANSPORT_SELECTION_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
