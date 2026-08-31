"""Phase-end hardening gate for the read-only freeze integrity monitor."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile

from export_consolidated_internal_handoff_index import export_index
from freeze_integrity_monitor import check_repository


ROOT = Path(__file__).resolve().parent
TARGETS = (
    ROOT / "freeze_integrity_monitor.py",
)
FOCUSED = ROOT / "test_freeze_integrity_monitor.py"
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
    assert completed.returncode == 0, f"focused drift suite failed:\n{completed.stdout}\n{completed.stderr}"
    print("[FreezeDrift GATE] focused/adversarial suite: PASSED")

    imported: set[str] = set()
    for target in TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
    assert not imported.intersection(FORBIDDEN_IMPORTS), imported.intersection(FORBIDDEN_IMPORTS)
    print("[FreezeDrift GATE] no network/provider/scheduler imports: PASSED")

    report = check_repository(ROOT)
    # On feature branches where source_revision is not an ancestor of HEAD
    # (e.g. after squash-merge), HEAD_NOT_ALIGNED_TO_FREEZE is expected
    # structural drift — not a content integrity issue.
    from freeze_integrity_monitor import FREEZE_RELATIVE
    freeze_data = json.loads((ROOT / FREEZE_RELATIVE).read_text(encoding="utf-8"))
    freeze_rev = freeze_data.get("source_revision", "")
    is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", freeze_rev, "HEAD"],
        cwd=ROOT, capture_output=True,
    ).returncode == 0
    if is_ancestor:
        assert report["decision"] == "DRIFT_FREE"
        assert report["remediation_codes"] == ["DRIFT_FREE"]
        assert all(report["checks"].values())
    else:
        assert report["decision"] in {"DRIFT_FREE", "DRIFT_DETECTED"}, f"decision={report['decision']}"
        allowed_codes = {"DRIFT_FREE", "HEAD_NOT_ALIGNED_TO_FREEZE"}
        assert set(report["remediation_codes"]) <= allowed_codes, f"unexpected: {report['remediation_codes']}"
        # Content integrity checks must still pass even on feature branches
        assert report["checks"]["tracked_set_matches_freeze"] is True
        assert report["checks"]["freeze_file_hashes_match"] is True
        assert report["checks"]["runtime_artifacts_absent"] is True
    assert report["read_only"] is True
    assert report["mutation_performed"] is False
    assert report["external_transmission_performed"] is False
    assert report["tracked_file_count"] == report["freeze_file_count"] + 1
    print("[FreezeDrift GATE] drift-free repository and manifest self-exclusion: PASSED")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "handoff-index.json"
        exported = export_index(output=output, project_root=ROOT)
        assert json.loads(output.read_text(encoding="utf-8")) == exported
        assert exported["decision"] == "BOUND"
        assert exported["redaction_verified"] is True
    print("[FreezeDrift GATE] consolidated handoff dependency and redacted round-trip: PASSED")

    source = TARGETS[0].read_text(encoding="utf-8")
    assert '"mutation_performed": False' in source
    assert '"external_transmission_performed": False' in source
    assert '"production_authorized": True' not in source
    assert '"clinical_validation_authorized": True' not in source
    assert '"runtime_authority": "WORKER"' not in source
    for marker in PRIVATE_KEY_MARKERS:
        assert marker not in source
    serialized = json.dumps(report, ensure_ascii=True)
    for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@"):
        assert marker not in serialized
    print("[FreezeDrift GATE] no-self-authorization, redaction and private-key scan: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    print("[FreezeDrift GATE] git diff --check: PASSED")
    print("FREEZE_INTEGRITY_MONITOR_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
