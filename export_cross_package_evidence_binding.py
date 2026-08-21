"""Export consolidated cross-package evidence binding status."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any

from cross_package_evidence_binding import check_repository

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
    report = check_repository(project_root)
    evidence: dict[str, Any] = {
        "evidence_type": "CROSS_PACKAGE_EVIDENCE_BINDING",
        "schema_version": report["schema_version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_revision": _source_revision(project_root),
        "decision": report["decision"],
        "remediation_codes": report["remediation_codes"],
        "checks": report["checks"],
        "refs": report["refs"],
        "source_revisions": report["source_revisions"],
        "freeze_source_revision": report["freeze_source_revision"],
        "artifact_hashes": report["artifact_hashes"],
        "read_only": True,
        "external_transmission_performed": False,
        "authorization_boundary": report["authorization_boundary"],
        "claim_boundary": report["claim_boundary"],
    }
    serialized = json.dumps(evidence, sort_keys=True, ensure_ascii=True)
    evidence["redaction_verified"] = not any(
        marker in serialized
        for marker in (
            "HN-",
            "AN-",
            "patient_id",
            "patient_token",
            "PRIVATE KEY",
            "@",
        )
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "cross-package-binding-local.json"
    export_evidence(output=destination)
    print(destination)
