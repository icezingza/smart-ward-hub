"""Export durable worker replay evidence with source revision binding."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from durable_worker_replay_contract import run_rehearsal

ROOT = Path(__file__).resolve().parent


def _source_revision(project_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"


def export_evidence(output: Path | None = None, project_root: Path = ROOT) -> dict[str, Any]:
    report = run_rehearsal()
    evidence: dict[str, Any] = {
        "evidence_type": "DURABLE_WORKER_REPLAY",
        "schema_version": "durable-worker-replay-evidence-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": _source_revision(project_root),
        **report,
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "durable-worker-replay-local.json"
    export_evidence(output=destination)
    print(destination)
