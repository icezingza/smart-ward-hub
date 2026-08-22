"""Export the local-only P2-004 evidence sufficiency decision."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from p2_004_evidence_sufficiency import FREEZE_PATH, ROOT, evaluate_sufficiency


OUTPUT_PATH = Path("evals/micro_rag/evidence/p2-004-evidence-sufficiency-local.json")


def export_sufficiency(
    *,
    output: Path = ROOT / OUTPUT_PATH,
    aggregate_path: Path = ROOT / "evals/micro_rag/evidence/gemini-3-flash-v2-repeated-aggregate-20260820.json",
    freeze_path: Path = ROOT / FREEZE_PATH,
) -> dict[str, Any]:
    report = evaluate_sufficiency(aggregate_path=aggregate_path, freeze_path=freeze_path)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    exported = {
        **report,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_source_revision": freeze.get("source_revision"),
        "origin_main_revision": freeze.get("origin_main_revision"),
        "freeze_status": "PASS" if report["checks"].get("freeze_pass") else "BLOCKED",
        "redaction_verified": report["checks"].get("redaction_pass") is True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(exported, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exported


if __name__ == "__main__":
    result = export_sufficiency()
    print(result["decision"])
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
