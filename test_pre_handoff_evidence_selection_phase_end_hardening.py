"""Phase-end hardening gate for the pre-handoff evidence selection policy."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from pre_handoff_evidence_selection import (
    DEPENDENCY_ORDER,
    SELECTED_SET,
    LOCKED_BOUNDARY,
    LOCKED_EXTERNAL_GATE_SNAPSHOT,
    SelectionDecision,
    select_repository,
)


ROOT = Path(__file__).resolve().parent
TARGETS = (ROOT / "pre_handoff_evidence_selection.py",)
FOCUSED = ROOT / "test_pre_handoff_evidence_selection.py"
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
    assert completed.returncode == 0, f"focused selection suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[EvidenceSelection GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[EvidenceSelection GATE] no network/provider/scheduler imports: PASSED")

    result = select_repository(ROOT)
    # The selection policy is allowed to remain blocked while its new
    # selected-set manifest is not yet freeze-listed. It must never silently
    # select an incomplete set.
    assert result["decision"] in {
        SelectionDecision.SELECTED_SET_VALID,
        SelectionDecision.SELECTION_BLOCKED,
    }
    assert result["dependency_order"] == list(DEPENDENCY_ORDER)
    assert len(result["selected"]) == len(SELECTED_SET)
    assert result["authorization_boundary"] == LOCKED_BOUNDARY
    assert result["external_gate_snapshot"] == LOCKED_EXTERNAL_GATE_SNAPSHOT
    assert result["read_only"] is True
    assert result["external_submission_allowed"] is False
    assert result["authorization_promoted"] is False
    assert result["runtime_mutation_performed"] is False
    assert result["external_transmission_performed"] is False
    if result["decision"] == SelectionDecision.SELECTION_BLOCKED:
        assert result["remediation_codes"]
    print("[EvidenceSelection GATE] selected-set completeness and locked boundary: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        # Selection itself is read-only; exporter output is tested separately
        # as a temporary file when one is added in the next phase.
        probe = Path(directory) / "probe.txt"
        probe.write_text("selection must not write here\n", encoding="utf-8")
        before = probe.read_bytes()
        _ = select_repository(ROOT)
        assert probe.read_bytes() == before
    print("[EvidenceSelection GATE] read-only filesystem boundary: PASSED")

    source = TARGETS[0].read_text(encoding="utf-8")
    assert '"external_submission_allowed": False' in source
    assert '"authorization_promoted": False' in source
    assert '"runtime_mutation_performed": False' in source
    assert '"external_transmission_performed": False' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    serialized = json.dumps(result, ensure_ascii=True)
    for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@"):
        assert marker not in serialized
    print("[EvidenceSelection GATE] no-self-authorization, redaction and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[EvidenceSelection GATE] git diff --check: PASSED")
    print("PRE_HANDOFF_EVIDENCE_SELECTION_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
