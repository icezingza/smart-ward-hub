"""Export the local-only P2-002 adapter conformance snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from p2_002_adapter_conformance import check_conformance


ROOT = Path(__file__).resolve().parent
FREEZE_PATH = ROOT / "evals" / "micro_rag" / "evidence" / "release-candidate-freeze-20260820.json"


def _freeze_metadata() -> dict[str, object]:
    try:
        payload = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"freeze_status": "UNREADABLE", "source_revision": None, "origin_main_revision": None}
    if not isinstance(payload, dict):
        return {"freeze_status": "INVALID", "source_revision": None, "origin_main_revision": None}
    return {
        "freeze_status": payload.get("freeze_status"),
        "source_revision": payload.get("source_revision"),
        "origin_main_revision": payload.get("origin_main_revision"),
    }


def export_conformance(output: Path | None = None, project_root: Path = ROOT) -> dict[str, object]:
    result = check_conformance()
    freeze = _freeze_metadata()
    evidence: dict[str, object] = {
        "evidence_type": result["evidence_type"],
        "schema_version": result["schema_version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": result["decision"],
        "remediation_codes": result["remediation_codes"],
        "checks": result["checks"],
        "transports": result["transports"],
        "selected_software_transport": result["selected_software_transport"],
        "hardware_evidence": result["hardware_evidence"],
        "fixture_only": True,
        "normalized_by_transport": result["normalized_by_transport"],
        "failure_matrix": result["failure_matrix"],
        "freeze_status": freeze["freeze_status"],
        "freeze_source_revision": freeze["source_revision"],
        "origin_main_revision": freeze["origin_main_revision"],
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
        marker in serialized for marker in ("patient_id", "patient_token", "HN-", "AN-", "PRIVATE KEY", "@")
    )
    if output is not None:
        output = (project_root / output).resolve() if not output.is_absolute() else output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    destination = ROOT / "evals" / "micro_rag" / "evidence" / "p2-002-adapter-conformance-local.json"
    export_conformance(output=destination)
    print(destination)
