"""Export the verified local-only P4 reviewer read-back decision guard evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from p4_reviewer_readback_decision_guard import ROOT, evaluate_readback_guard


OUTPUT_PATH = Path("evals/micro_rag/evidence/p4-reviewer-readback-decision-guard-local.json")
_REDACTION_MARKERS = (
    "patient_id",
    "patient_token",
    "private key",
    "bearer ",
    "password",
    "api_key",
    "@",
)


def export_reviewer_readback_decision_guard(*, output: Path = ROOT / OUTPUT_PATH) -> dict[str, Any]:
    report = evaluate_readback_guard()
    if report["decision"] != "P4_REVIEWER_READBACK_GUARD_VERIFIED":
        raise RuntimeError("read-back decision guard is not verified; export refused")

    serialized_report = json.dumps(report, ensure_ascii=True, sort_keys=True).lower()
    redaction_verified = not any(marker in serialized_report for marker in _REDACTION_MARKERS)
    if not redaction_verified:
        raise RuntimeError("redaction marker detected; export refused")

    exported = {
        **report,
        "evidence_scope": "LOCAL_DETERMINISTIC_FIXTURE_ONLY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "redaction_verified": True,
        "external_submission_allowed": False,
        "external_transmission_performed": False,
        "external_readback_trusted": False,
        "external_decision_verified": False,
        "authorization_promoted": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(exported, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exported


if __name__ == "__main__":
    result = export_reviewer_readback_decision_guard()
    print(result["decision"])
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
