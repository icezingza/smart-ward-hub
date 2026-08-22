"""Export a redacted selection-to-manifest consistency record."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from pre_handoff_selection_manifest_consistency import check_repository


ROOT = Path(__file__).resolve().parent


def export_consistency(output: Path | None = None, project_root: Path = ROOT) -> dict:
    result = check_repository(project_root)
    evidence = {
        "evidence_type": "PRE_HANDOFF_SELECTION_MANIFEST_CONSISTENCY",
        "schema_version": result["schema_version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": result["decision"],
        "remediation_codes": result["remediation_codes"],
        "checks": result["checks"],
        "selected_set_decision": result["selected_set_decision"],
        "pre_handoff_decision": result["pre_handoff_decision"],
        "manifest_decision": result["manifest_decision"],
        "selected_count": result["selected_count"],
        "dependency_order": result["dependency_order"],
        "freeze_source_revision": result["freeze_source_revision"],
        "origin_main_revision": result["origin_main_revision"],
        "external_gate_snapshot": result["external_gate_snapshot"],
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
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "pre-handoff-selection-manifest-consistency-local.json"
    export_consistency(output=destination)
    print(destination)
