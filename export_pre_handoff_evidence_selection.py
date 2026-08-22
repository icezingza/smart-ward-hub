"""Export a redacted internal pre-handoff evidence selection record."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from pre_handoff_evidence_selection import select_repository


ROOT = Path(__file__).resolve().parent


def export_selection(output: Path | None = None, project_root: Path = ROOT) -> dict:
    selection = select_repository(project_root)
    evidence = {
        "evidence_type": "PRE_HANDOFF_EVIDENCE_SELECTION",
        "schema_version": selection["schema_version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": selection["decision"],
        "remediation_codes": selection["remediation_codes"],
        "checks": selection["checks"],
        "dependency_order": selection["dependency_order"],
        "selected": selection["selected"],
        "excluded": selection["excluded"],
        "freeze_source_revision": selection["freeze_source_revision"],
        "origin_main_revision": selection["origin_main_revision"],
        "external_gate_snapshot": selection["external_gate_snapshot"],
        "claim_boundary": selection["claim_boundary"],
        "authorization_boundary": selection["authorization_boundary"],
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
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "pre-handoff-evidence-selection-local.json"
    export_selection(output=destination)
    print(destination)
