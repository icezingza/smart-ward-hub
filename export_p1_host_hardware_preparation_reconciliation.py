"""Export local-only host-hardware preparation reconciliation evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from p1_host_hardware_preparation_reconciliation import evaluate_host_hardware_preparation


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "evals/micro_rag/evidence/p1-host-hardware-preparation-reconciliation-local.json"
EXPORT_SCHEMA_VERSION = "p1-host-hardware-preparation-reconciliation-evidence-v1"


def export_evidence(output: Path = DEFAULT_OUTPUT) -> dict:
    report = evaluate_host_hardware_preparation()
    if not report["all_passed"]:
        raise RuntimeError("cannot export failed host-hardware preparation reconciliation")
    evidence = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "evidence_type": report["evidence_type"],
        "decision": report["decision"],
        "evidence_scope": report["mode"],
        "source_module": "p1_host_hardware_preparation_reconciliation.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "all_passed": report["all_passed"],
        "checks": report["checks"],
        "deployment_result": report["deployment_result"],
        "host_manifest_result": report["host_manifest_result"],
        "bench_packet_result": report["bench_packet_result"],
        "target_model": report["target_model"],
        "target_role": report["target_role"],
        "host_execution_status": report["host_execution_status"],
        "physical_validation": report["physical_validation"],
        "physical_execution_performed": False,
        "observed_result_count": 0,
        "clinical_validation": "PENDING",
        "real_target_host_evidence": "UNVERIFIED",
        "hardware_evidence": "UNVERIFIED",
        "ready_for_target_host_execution": False,
        "external_submission_allowed": False,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "authorization_promoted": False,
        "software_evidence_only": True,
        "fixture_only": True,
        "patient_data_used": False,
        "redaction_verified": True,
        "external_gate_snapshot": report["external_gate_snapshot"],
        "authorization_boundary": report["authorization_boundary"],
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "claim_boundary": "CONTROLLED_PRODUCTION_PROTOTYPE",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    evidence = export_evidence()
    print(json.dumps(evidence, ensure_ascii=True, sort_keys=True))
    print(f"P1_HOST_HARDWARE_PREPARATION_RECONCILIATION_EVIDENCE_EXPORTED={DEFAULT_OUTPUT}")
