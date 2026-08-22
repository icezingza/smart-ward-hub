"""Export local-only Wave 0 governance reconciliation evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from wave0_governance_reconciliation_guard import evaluate_wave0_governance_reconciliation


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "evals/micro_rag/evidence/wave0-governance-reconciliation-local.json"
EXPORT_SCHEMA_VERSION = "wave0-governance-reconciliation-evidence-v1"


def export_evidence(output: Path = DEFAULT_OUTPUT) -> dict:
    report = evaluate_wave0_governance_reconciliation()
    if not report["all_passed"]:
        raise RuntimeError("cannot export failed Wave 0 governance reconciliation")
    evidence = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "evidence_type": report["evidence_type"],
        "decision": report["decision"],
        "evidence_scope": report["mode"],
        "source_module": "wave0_governance_reconciliation_guard.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "all_passed": report["all_passed"],
        "checks": report["checks"],
        "package_pre_freeze": report["package_pre_freeze"],
        "appointment_templates": report["appointment_templates"],
        "appointment_plan_dependency": report["appointment_plan_dependency"],
        "external_gate_reconciliation": report["external_gate_reconciliation"],
        "external_gate_snapshot": report["external_gate_snapshot"],
        "ready_for_external_appointment": report["ready_for_external_appointment"],
        "ready_for_external_review": False,
        "appointment_confirmed": False,
        "submission_allowed": False,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "authorization_promoted": False,
        "software_evidence_only": True,
        "fixture_only": True,
        "patient_data_used": False,
        "hardware_evidence": "UNVERIFIED",
        "clinical_validation": "PENDING",
        "authorization_boundary": report["authorization_boundary"],
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "redaction_verified": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    evidence = export_evidence()
    print(json.dumps(evidence, ensure_ascii=True, sort_keys=True))
    print(f"WAVE0_GOVERNANCE_RECONCILIATION_EVIDENCE_EXPORTED={DEFAULT_OUTPUT}")
