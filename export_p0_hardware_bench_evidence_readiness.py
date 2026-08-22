"""Export local-only P0 hardware-bench evidence readiness."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from p0_hardware_bench_evidence_readiness import evaluate_hardware_bench_readiness


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "evals/micro_rag/evidence/p0-hardware-bench-evidence-readiness-local.json"
EXPORT_SCHEMA_VERSION = "p0-hardware-bench-evidence-readiness-evidence-v1"


def export_evidence(output: Path = DEFAULT_OUTPUT) -> dict:
    report = evaluate_hardware_bench_readiness()
    if not report["all_passed"]:
        raise RuntimeError("cannot export failed hardware-bench readiness")
    evidence = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "evidence_type": "P0_HARDWARE_BENCH_EVIDENCE_READINESS",
        "decision": report["decision"],
        "evidence_scope": report["mode"],
        "source_module": "p0_hardware_bench_evidence_readiness.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "all_passed": report["all_passed"],
        "checks": report["checks"],
        "target_model": report["target_model"],
        "target_role": report["target_role"],
        "packet_status": report["packet_status"],
        "physical_execution_performed": False,
        "physical_hardware_evidence": "UNVERIFIED",
        "preconditions_status": report["preconditions_status"],
        "bench_steps_status": report["bench_steps_status"],
        "precondition_count": report["precondition_count"],
        "bench_step_count": report["bench_step_count"],
        "stop_condition_count": report["stop_condition_count"],
        "observed_result_count": 0,
        "clinical_use_authorized": False,
        "external_submission_allowed": False,
        "external_transmission_performed": False,
        "authorization_promoted": False,
        "runtime_mutation_performed": False,
        "authorization_boundary": report["authorization_boundary"],
        "external_gate_snapshot": {"blocked": 7, "open": 3, "evidence_submitted": 0, "passed": 0},
        "patient_data_used": False,
        "raw_frames_recorded": False,
        "real_hardware_evidence": "UNVERIFIED",
        "real_his_evidence": "UNVERIFIED",
        "real_oidc_mtls_evidence": "UNVERIFIED",
        "redaction_verified": True,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    evidence = export_evidence()
    print(json.dumps(evidence, ensure_ascii=True, sort_keys=True))
    print(f"P0_HARDWARE_BENCH_EVIDENCE_READINESS_EXPORTED={DEFAULT_OUTPUT}")
