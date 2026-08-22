"""Export the dry-run external-gate transition guard evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from p3_external_gate_transition_guard import evaluate_transition_guard


ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = Path("evals/micro_rag/evidence/p3-external-gate-transition-guard-local.json")


def export_transition_guard(*, output: Path = ROOT / OUTPUT_PATH) -> dict[str, Any]:
    report = evaluate_transition_guard()
    exported = {
        **report,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "redaction_verified": report["checks"].get("lifecycle_text_redacted") is True,
        "external_submission_allowed": False,
        "external_transmission_performed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(exported, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exported


if __name__ == "__main__":
    result = export_transition_guard()
    print(result["decision"])
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
