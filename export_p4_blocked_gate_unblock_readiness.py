"""Export the seven blocked-gate unblock readiness matrix."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from p4_blocked_gate_unblock_readiness import ROOT, evaluate_p4_blocked_gate_readiness


OUTPUT_PATH = Path("evals/micro_rag/evidence/p4-blocked-gate-unblock-readiness-local.json")


def export_p4_readiness(*, output: Path = ROOT / OUTPUT_PATH) -> dict[str, Any]:
    report = evaluate_p4_blocked_gate_readiness()
    exported = {
        **report,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "redaction_verified": report["checks"].get("all_records_redacted") is True,
        "external_submission_allowed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(exported, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exported


if __name__ == "__main__":
    result = export_p4_readiness()
    print(result["decision"])
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
