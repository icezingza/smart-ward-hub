"""Export the read-only P2-005 worker-control consistency decision."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from p2_005_worker_control_consistency import ROOT, evaluate_worker_consistency


OUTPUT_PATH = Path("evals/micro_rag/evidence/p2-005-worker-control-consistency-local.json")


def export_worker_consistency(
    *,
    output: Path = ROOT / OUTPUT_PATH,
    project_root: Path = ROOT,
) -> dict[str, Any]:
    report = evaluate_worker_consistency(root=project_root)
    exported = {
        **report,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_status": "PASS" if report["checks"].get("freeze_bound_revision_present") else "BLOCKED",
        "redaction_verified": report["checks"].get("redaction_boundary_clean") is True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(exported, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exported


if __name__ == "__main__":
    result = export_worker_consistency()
    print(result["decision"])
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
