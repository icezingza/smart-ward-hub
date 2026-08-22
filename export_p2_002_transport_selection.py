"""Export the local-only P2-002 transport selection decision."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from p2_002_transport_selection import ROOT, evaluate_transport_selection


OUTPUT_PATH = Path("evals/micro_rag/evidence/p2-002-transport-selection-local.json")


def export_transport_selection(
    *,
    output: Path = ROOT / OUTPUT_PATH,
) -> dict[str, Any]:
    report = evaluate_transport_selection()
    exported = {
        **report,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "redaction_verified": report["checks"].get("conformance_evidence_redacted") is True,
        "freeze_binding_required": True,
        "external_transmission_performed": False,
        "external_submission_allowed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(exported, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exported


if __name__ == "__main__":
    result = export_transport_selection()
    print(result["decision"])
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
