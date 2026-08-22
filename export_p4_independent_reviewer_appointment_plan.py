"""Export the internal-only independent reviewer appointment plan."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from p4_independent_reviewer_appointment_plan import evaluate_appointment_plan


ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = Path("evals/micro_rag/evidence/p4-independent-reviewer-appointment-plan-local.json")


def export_appointment_plan(*, output: Path = ROOT / OUTPUT_PATH) -> dict[str, Any]:
    report = evaluate_appointment_plan()
    exported = {
        **report,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "redaction_verified": report["checks"].get("plan_redacted") is True,
        "submission_allowed": False,
        "appointment_confirmed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(exported, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exported


if __name__ == "__main__":
    result = export_appointment_plan()
    print(result["decision"])
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
