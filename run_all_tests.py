import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TESTS = [
    "test_pairing.py",
    "test_telemetry.py",
    "test_triage.py",
    "test_forensics.py",
    "test_fhir.py",
    "test_security.py",
    "test_auth_fail_closed.py",
    "test_edge_runtime.py",
    "test_p0_hardening.py",
    "test_p0_oidc_config.py",
    "test_p0_mtls_config.py",
    "test_p0_recovery.py",
    "test_p0_his_admission_contract.py",
    "test_power_loss_recovery_harness.py",
    "test_backup_restore.py",
    "test_deployment_readiness.py",
    "test_p1_002_host_hardening_readiness.py",
    "test_key_custody_contract.py",
    "test_key_custody_contract_negative.py",
    "test_p1_003_phase_end_hardening_gate.py",
    "test_external_anchor_contract.py",
    "test_external_anchor_fault_injection.py",
    "test_p1_004_phase_end_hardening_gate.py",
    "test_file_anchor_store.py",
    "test_clinical_shadow_mode.py",
    "test_clinical_shadow_mode_negative.py",
    "test_p1_005_phase_end_hardening_gate.py",
    "test_clinical_validation_readiness.py",
    "test_p1_006_phase_end_hardening_gate.py",
    "test_external_validation_package.py",
    "test_external_validation_gate_matrix.py",
    "test_p1_007_phase_end_hardening_gate.py",
    "test_gv10_evidence.py",
    "test_independent_review_operations.py",
    "test_p1_008_phase_end_hardening_gate.py",
    "test_wave0_owner_appointment_phase_end_hardening.py",
    "test_persistence_contract.py",
    "test_repeated_sample_evaluation.py",
    "test_runtime_semantic_retrieval_readiness.py",
    "test_p2_004_review_and_handoff.py",
    "test_controlled_pilot_operations.py",
    "test_controlled_pilot_blocker_analysis.py",
    "test_wave0_governance.py",
    "test_external_authorization_api_simulator.py",
    "test_wave_e_evidence.py",
    "test_wave1_external_execution_readiness.py",
    "test_wave0_owner_appointment_intake.py",
    "test_wave1_software_preparation.py",
    "test_wave1_software_preparation_phase_end_hardening.py",
    "test_release_freeze_candidate.py",
    "test_production_readiness_audit.py",
    "evals/micro_rag/test_hallucination_suite.py",
    "evals/micro_rag/test_response_adapter.py",
    "evals/micro_rag/test_registry_index.py",
    "evals/micro_rag/test_registry_backed_evaluation.py",
    "test_p2_edge_iot_adapters.py",
    "test_serial_framing.py",
    "test_network_pressure_simulation.py",
    "test_serial_bench_runner.py",
    "test_residual_controls.py",
    "test_device_trust.py",
    "test_device_trust_observe.py",
    "test_session_workflows.py",
    "test_outside_admission.py",
    "test_roaming.py",
    "validate_reliability.py",
    "simulate_pilot_30days.py",
]


def run() -> None:
    print("=" * 72)
    print("SMART WARD HUB MASTER REGRESSION SUITE")
    print("=" * 72)
    for script in TESTS:
        print(f"\n[MASTER] Running {script}")
        completed = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT)
        if completed.returncode != 0:
            raise SystemExit(f"[MASTER] FAILED: {script}")
        print(f"[MASTER] PASSED: {script}")
    print("\nALL FUNCTIONAL LEVEL 1–6, DEVICE TRUST, WARD WORKFLOW, OUTSIDE-IN ADMISSION, AND ROAMING CHECKS PASSED")
    print("Note: Phase 6, Device Trust, ward workflow, Outside-in admission, and roaming verification are software tests, not clinical, HIS, or hardware validation.")


if __name__ == "__main__":
    run()
