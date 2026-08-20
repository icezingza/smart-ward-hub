from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from p1_008_independent_review_readiness import template, validate_manifest


ROOT = Path(__file__).resolve().parent
FOCUSED_TESTS = (
    "test_independent_review_operations.py",
    "test_p1_008_independent_review_hardening.py",
)
FORBIDDEN_PRIVATE_MARKERS = (
    "-" * 5 + "BEGIN RSA " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN EC " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN OPENSSH " + "PRIVATE KEY" + "-" * 5,
    "-" * 5 + "BEGIN " + "PRIVATE KEY" + "-" * 5,
)


def run() -> None:
    for script in FOCUSED_TESTS:
        completed = subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True)
        if completed.returncode != 0:
            raise AssertionError(f"{script} failed:\n{completed.stdout}\n{completed.stderr}")
        print(f"[P1-008 GATE] {script}: PASSED")

    template_path = ROOT / "evals/micro_rag/evidence/p1-008-independent-review-readiness-template-20260821.json"
    schema_path = ROOT / "evals/micro_rag/evidence/p1-008-independent-review-readiness-schema-v1.json"
    if not template_path.is_file() or not schema_path.is_file():
        raise AssertionError("P1-008 readiness template/schema artifacts are missing; run exporter first")
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_manifest(payload, template_only=True)["valid"] is True
    assert schema["$id"].endswith("p1-008-independent-review-readiness-v1")
    assert payload["track_count"] == 7
    assert payload["software_track_status_counts"] == {"SOFTWARE_VERIFIED": 7}
    assert payload["external_review_status_counts"] == {"PENDING_EXTERNAL_REVIEW": 7}
    assert payload["review_session_status"] == "SOFTWARE_DRY_RUN_VERIFIED"
    assert payload["external_review_status"] == "PENDING_EXTERNAL_REVIEW"
    assert payload["external_owner_appointment"] == "PENDING_EXTERNAL_APPOINTMENT"
    assert payload["real_world_authorization"] is False
    assert payload["clinical_validation_authorized"] is False
    assert payload["production_authorized"] is False
    assert payload["software_evidence_only"] is True
    assert payload["authorization_boundary"]["external_authority"] == "NONE"
    assert payload["authorization_boundary"]["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert len(payload["tracks"]) == 7
    print("[P1-008 GATE] Readiness template/schema, IR-001..IR-007 coverage and no-authorization boundary: PASSED")

    scanned = [
        ROOT / "independent_review_operations.py",
        ROOT / "p1_008_independent_review_readiness.py",
        ROOT / "export_p1_008_independent_review_readiness.py",
        ROOT / "P1_008_INDEPENDENT_REVIEW_READINESS_REPORT.md",
        template_path,
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in FORBIDDEN_PRIVATE_MARKERS), path
    print("[P1-008 GATE] Private-key block scan on runtime/readiness artifacts: PASSED")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    if diff_check.returncode != 0:
        raise AssertionError(f"git diff --check failed:\n{diff_check.stdout}\n{diff_check.stderr}")
    print("[P1-008 GATE] git diff --check: PASSED")
    print("P1_008_PHASE_END_HARDENING_GATE_PASSED")


if __name__ == "__main__":
    run()
