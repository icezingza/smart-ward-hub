from pathlib import Path
import subprocess
import sys


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
    "test_key_custody_contract.py",
    "test_key_custody_contract_negative.py",
    "test_external_anchor_contract.py",
    "test_external_anchor_fault_injection.py",
    "test_file_anchor_store.py",
    "test_clinical_shadow_mode.py",
    "test_clinical_shadow_mode_negative.py",
    "test_clinical_validation_readiness.py",
    "test_external_validation_package.py",
    "test_external_validation_gate_matrix.py",
    "test_gv10_evidence.py",
    "test_independent_review_operations.py",
    "evals/micro_rag/test_hallucination_suite.py",
    "evals/micro_rag/test_response_adapter.py",
    "evals/micro_rag/test_registry_index.py",
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
