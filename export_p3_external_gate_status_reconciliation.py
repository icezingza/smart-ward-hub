"""Export the reconciled ten-gate external-validation status."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from p3_external_gate_status_reconciliation import ROOT, reconcile_external_gates


OUTPUT_PATH = Path("evals/micro_rag/evidence/p3-external-gate-status-reconciliation-local.json")


def export_external_gate_status(
    *,
    output: Path = ROOT / OUTPUT_PATH,
) -> dict[str, Any]:
    report = reconcile_external_gates()
    exported = {
        **report,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "redaction_verified": report["checks"].get("all_gate_text_is_redacted") is True,
        "external_submission_allowed": False,
        "external_transmission_performed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(exported, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exported


if __name__ == "__main__":
    result = export_external_gate_status()
    print(result["decision"])
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
