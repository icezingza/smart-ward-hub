"""Run the bounded, synthetic-only software simulation matrix.

This runner is deliberately not a load generator and never contacts hardware,
hospital systems, identity providers, or network hosts.  A PASS means the named
software fixtures passed, not that the corresponding real-world gate is closed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
import sys
from typing import Callable


ROOT = Path(__file__).resolve().parent
EVIDENCE_CLASS = "LOCAL_SYNTHETIC_SOFTWARE_SIMULATION"


@dataclass(frozen=True)
class SimulationDomain:
    domain_id: str
    feature_or_risk: str
    scripts: tuple[str, ...]
    coverage: str
    residual_risk: str


@dataclass(frozen=True)
class ExternalGate:
    gate_id: str
    feature_or_risk: str
    reason_not_simulated: str
    required_evidence: str


SOFTWARE_DOMAINS = (
    SimulationDomain("SIM-001", "Smart Watch telemetry contract and replay handling", ("test_smartwatch_simulator.py", "test_p2_edge_iot_adapters.py"), "normal, replay, out-of-order, disconnect/reconnect, malformed envelope, PII and command rejection", "does not prove sensor accuracy, BLE radio, firmware, battery, or wearer safety"),
    SimulationDomain("SIM-002", "Transport pressure and bounded ingestion", ("test_network_pressure_simulation.py", "test_serial_framing.py", "test_serial_bench_runner.py"), "burst, partial frames, CRC corruption, duplicate, malformed, PII, queue pressure and reconnect", "does not prove physical cable, driver, RF, broker, AP, or host performance"),
    SimulationDomain("SIM-003", "Authentication, pairing and device trust", ("test_auth_fail_closed.py", "test_pairing.py", "test_security.py", "test_device_trust.py", "test_device_trust_observe.py"), "missing credentials, scopes, pairing, signature and trust lifecycle boundaries", "does not prove real IdP, HSM, manufacturer key custody, revocation distribution, or mTLS handshake"),
    SimulationDomain("SIM-004", "Ward sessions and operator workflow", ("test_session_workflows.py", "test_outside_admission.py", "test_roaming.py"), "session lifecycle, admission preparation, scoped commands, idempotency and roaming revision checks", "does not prove usability, training effectiveness, workflow adoption, or clinical safety"),
    SimulationDomain("SIM-005", "Alert and shadow-mode safety boundaries", ("test_triage.py", "test_alert_sync_reconciliation_matrix.py", "test_clinical_shadow_mode.py", "test_clinical_shadow_mode_negative.py"), "alert reconciliation, stale revisions, forbidden diagnostic labels, duplicate review and notification gates", "does not prove clinical sensitivity, specificity, alarm burden, or clinical governance approval"),
    SimulationDomain("SIM-006", "Persistence, recovery and storage faults", ("test_p0_recovery.py", "test_power_loss_recovery_harness.py", "test_cross_component_recovery_matrix.py", "test_backup_restore.py"), "checkpoint corruption, database/WAL faults, disk-full injection, tamper, backup/restore and reconciliation-required decisions", "does not prove physical power cut, host disk failure, ransomware recovery, or separate-site restore"),
    SimulationDomain("SIM-007", "Audit and forensic integrity", ("test_forensics.py", "test_file_anchor_store.py", "test_external_anchor_fault_injection.py"), "local chain verification, tamper detection and failed anchor handling", "does not prove independent WORM custody, trusted timestamps, or legal admissibility"),
    SimulationDomain("SIM-008", "HIS/FHIR and downstream failure handling", ("test_fhir.py", "test_p0_his_admission_contract.py", "test_p0_his_fhir_contract_readiness_guard.py"), "opaque token boundary, structured acknowledgement, mismatch, timeout and retention behavior", "does not prove real HIS endpoint, hospital authorization, certificate interoperability, or live data mapping"),
    SimulationDomain("SIM-009", "Durable worker and retry controls", ("test_durable_worker_store.py", "test_durable_worker_replay_contract.py", "test_worker_queue_backup.py", "test_worker_recovery_approval.py"), "bounded retries, dead-letter eligibility, queue backup and approval requirements", "does not prove distributed worker availability or external queue delivery"),
    SimulationDomain("SIM-010", "Configuration and Windows deployment safety", ("test_p0_oidc_config.py", "test_p0_mtls_config.py", "test_p0_hardening.py", "test_deployment_readiness.py"), "fail-closed configuration, Windows ACL key hygiene, migration-first startup and deployment contract", "does not prove host hardening, firewall, secure boot, certificate rotation, or operator account controls"),
)

EXTERNAL_GATES = (
    ExternalGate("EXT-001", "Smart Watch sensors and firmware", "Requires the exact device, firmware and non-clinical bench fixture.", "packet trace, firmware version, BLE/radio range, battery and fault-injection evidence"),
    ExternalGate("EXT-002", "Hub hardware and power", "Software cannot cut power, exhaust real storage, or verify physical tamper resistance safely.", "host hardening record, UPS/power-cut drill, disk and restore evidence"),
    ExternalGate("EXT-003", "Identity and transport", "Real OIDC, mTLS and network segmentation require an authorized tenant and network.", "IdP/mTLS handshake, rotation, revocation and firewall evidence"),
    ExternalGate("EXT-004", "HIS/FHIR interoperability", "A local contract fixture is not an authorized hospital exchange.", "sandbox transcript, structured acknowledgement and failure-recovery evidence"),
    ExternalGate("EXT-005", "Clinical safety and human factors", "Synthetic telemetry cannot establish clinical benefit or safe operator behavior.", "approved protocol, training, shadow-mode review and clinical owner decision"),
    ExternalGate("EXT-006", "Privacy, legal and independent custody", "Code cannot grant legal approval or independent evidence custody.", "privacy/legal review, retention decision, external WORM/timestamp and independent review"),
)


def run_matrix(
    *,
    execute: bool,
    timeout_seconds: int = 90,
    root: Path = ROOT,
    domain_ids: tuple[str, ...] | None = None,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, object]:
    selected_ids = set(domain_ids or ())
    known_ids = {domain.domain_id for domain in SOFTWARE_DOMAINS}
    unknown_ids = selected_ids - known_ids
    if unknown_ids:
        raise ValueError(f"unknown simulation domain: {', '.join(sorted(unknown_ids))}")
    domains = tuple(domain for domain in SOFTWARE_DOMAINS if not selected_ids or domain.domain_id in selected_ids)
    results: list[dict[str, object]] = []
    all_passed = True
    for domain in domains:
        script_results: list[dict[str, object]] = []
        for script in domain.scripts:
            path = root / script
            row: dict[str, object] = {"script": script}
            if not path.is_file():
                row.update(status="FAILED", reason="script_not_found")
                all_passed = False
            elif not execute:
                row.update(status="NOT_EXECUTED", reason="explicit_execute_flag_required")
            else:
                try:
                    print(f"[Simulation Matrix] Running {domain.domain_id}: {script}", file=sys.stderr, flush=True)
                    completed = command_runner(
                        [sys.executable, str(path)], cwd=root, capture_output=True, text=True, timeout=timeout_seconds, check=False
                    )
                    row.update(status="PASSED" if completed.returncode == 0 else "FAILED", returncode=completed.returncode)
                    if completed.returncode != 0:
                        row["reason"] = "script_failed"
                        all_passed = False
                except subprocess.TimeoutExpired:
                    row.update(status="FAILED", reason="timeout")
                    all_passed = False
            script_results.append(row)
        results.append({**asdict(domain), "status": "PASSED" if all(item["status"] == "PASSED" for item in script_results) else ("NOT_EXECUTED" if not execute else "FAILED"), "scripts": script_results})
    return {
        "schema_version": "smart-ward-hub-software-simulation-matrix-v1",
        "evidence_class": EVIDENCE_CLASS,
        "execution_mode": "EXECUTED" if execute else "PLAN_ONLY",
        "software_simulation_passed": all_passed if execute else False,
        "software_domains": results,
        "external_unverified_gates": [asdict(gate) for gate in EXTERNAL_GATES],
        "patient_data_used": False,
        "hardware_contacted": False,
        "external_network_contacted": False,
        "clinical_validation_authorized": False,
        "production_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bounded synthetic Smart Ward Hub simulation matrix.")
    parser.add_argument("--execute", action="store_true", help="Run local software fixtures; otherwise print the coverage plan.")
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--domain", action="append", choices=[domain.domain_id for domain in SOFTWARE_DOMAINS], help="Run only one or more named software domains.")
    args = parser.parse_args()
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be at least 1")
    report = run_matrix(execute=args.execute, timeout_seconds=args.timeout_seconds, domain_ids=tuple(args.domain) if args.domain else None)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not args.execute or report["software_simulation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
