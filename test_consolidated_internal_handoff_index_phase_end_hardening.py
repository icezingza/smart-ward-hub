"""Phase-end hardening gate for the consolidated internal handoff index."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from consolidated_internal_handoff_index import LOCKED_BOUNDARY, LOCKED_EXTERNAL_GATE_SNAPSHOT, build_index
from export_consolidated_internal_handoff_index import export_index


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "consolidated_internal_handoff_index.py",
    ROOT / "export_consolidated_internal_handoff_index.py",
)
FOCUSED = ROOT / "test_consolidated_internal_handoff_index.py"
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
    assert completed.returncode == 0, f"focused index suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[HandoffIndex GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[HandoffIndex GATE] no network/provider/scheduler imports: PASSED")

    result = build_index(ROOT)
    assert result.decision == "BOUND"
    assert result.remediation_codes == ("HANDOFF_INDEX_BOUND",)
    index = result.index
    assert index["read_only"] is True
    assert index["external_submission_allowed"] is False
    assert index["authorization_promoted"] is False
    assert index["runtime_mutation_performed"] is False
    assert index["authorization_boundary"] == LOCKED_BOUNDARY
    assert index["freeze"]["external_gate_snapshot"] == LOCKED_EXTERNAL_GATE_SNAPSHOT
    assert index["claim_boundary"]["production_ready"] is False
    assert index["claim_boundary"]["clinical_validation"] == "PENDING"
    assert len(index["evidence_navigation"]) == 4
    print("[HandoffIndex GATE] binding, navigation and locked claim/gate boundary: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "handoff-index.json"
        evidence = export_index(output=output, project_root=ROOT)
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved == evidence
        assert evidence["decision"] == "BOUND"
        assert evidence["redaction_verified"] is True
        assert evidence["external_submission_allowed"] is False
        assert evidence["authorization_promoted"] is False
    print("[HandoffIndex GATE] redacted exporter round-trip: PASSED")

    source = "\n".join(target.read_text(encoding="utf-8") for target in TARGETS)
    assert '"external_submission_allowed": False' in source
    assert '"authorization_promoted": False' in source
    assert '"runtime_mutation_performed": False' in source
    assert '"production_ready": False' in source
    assert '"clinical_validation": "PENDING"' in source
    assert '"passed": 0' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    serialized = json.dumps(evidence, ensure_ascii=True)
    for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@"):
        assert marker not in serialized
    print("[HandoffIndex GATE] no-self-authorization, redaction and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[HandoffIndex GATE] git diff --check: PASSED")
    print("CONSOLIDATED_INTERNAL_HANDOFF_INDEX_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
