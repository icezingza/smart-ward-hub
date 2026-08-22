"""Export a redacted local repository visibility governance snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from repository_visibility_governance import check_repository


ROOT = Path(__file__).resolve().parent


def export_visibility(output: Path | None = None, project_root: Path = ROOT) -> dict:
    result = check_repository(project_root)
    evidence = {
        "evidence_type": result["evidence_type"],
        "schema_version": result["schema_version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": result["decision"],
        "remediation_codes": result["remediation_codes"],
        "checks": result["checks"],
        "repository": result["repository"],
        "is_private": result["is_private"],
        "default_branch": result["default_branch"],
        "observation_source": result["observation_source"],
        "claim_boundary": result["claim_boundary"],
        "authorization_boundary": result["authorization_boundary"],
        "read_only": True,
        "external_submission_allowed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "external_transmission_performed": False,
    }
    serialized = json.dumps(evidence, sort_keys=True, ensure_ascii=True)
    evidence["redaction_verified"] = not any(
        marker in serialized
        for marker in ("HN-", "AN-", "patient_id", "patient_token", "PRIVATE KEY", "@")
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "repository-visibility-governance-local.json"
    export_visibility(output=destination)
    print(destination)
