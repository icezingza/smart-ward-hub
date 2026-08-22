"""Local-only transport selection gate for the first P2-002 software profile."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from p2_002_adapter_conformance import check_conformance


ROOT = Path(__file__).resolve().parent
SELECTED_SOFTWARE_TRANSPORT = "serial"
CANDIDATE_TRANSPORTS = ("mqtt", "websocket", "serial", "ble")
PHYSICAL_GATE_STATUS = "NOT_STARTED"
EXPECTED_HARDWARE_EVIDENCE = "UNVERIFIED"
EXPECTED_BOUNDARY = {
    "external_authority": "NONE",
    "clinical_validation_authorized": False,
    "production_authorized": False,
    "runtime_authority": "NONE",
    "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
}
FORBIDDEN_MARKERS = (
    "HN-",
    "AN-",
    "MRN",
    "patient_id",
    "patient_token",
    "patient_name",
    "private key",
    "bearer ",
    "password",
    "api_key",
    "@",
)


class TransportSelectionError(ValueError):
    """Raised when a selection input cannot be evaluated safely."""


def evaluate_transport_selection() -> dict[str, Any]:
    conformance = check_conformance()
    checks: dict[str, bool] = {}
    remediation_codes: list[str] = []

    checks["selected_transport_allowlisted"] = SELECTED_SOFTWARE_TRANSPORT in CANDIDATE_TRANSPORTS
    if not checks["selected_transport_allowlisted"]:
        remediation_codes.append("SELECTED_TRANSPORT_NOT_ALLOWLISTED")
    checks["serial_selected_as_first_profile"] = SELECTED_SOFTWARE_TRANSPORT == "serial"
    if not checks["serial_selected_as_first_profile"]:
        remediation_codes.append("FIRST_TRANSPORT_SELECTION_CHANGED")
    checks["conformance_decision_verified"] = conformance.get("decision") == "P2_002_ADAPTER_CONFORMANCE_VERIFIED"
    if not checks["conformance_decision_verified"]:
        remediation_codes.append("ADAPTER_CONFORMANCE_NOT_VERIFIED")
    checks["all_candidates_conform"] = (
        conformance.get("transports") == list(CANDIDATE_TRANSPORTS)
        and conformance.get("checks", {}).get("all_transports_normalized") is True
        and conformance.get("checks", {}).get("failure_matrix_complete") is True
    )
    if not checks["all_candidates_conform"]:
        remediation_codes.append("TRANSPORT_CONFORMANCE_MATRIX_INCOMPLETE")
    checks["selected_transport_in_conformance"] = SELECTED_SOFTWARE_TRANSPORT in conformance.get("transports", [])
    if not checks["selected_transport_in_conformance"]:
        remediation_codes.append("SELECTED_TRANSPORT_NOT_CONFORMANCE_TESTED")
    checks["hardware_gate_not_promoted"] = PHYSICAL_GATE_STATUS == "NOT_STARTED"
    if not checks["hardware_gate_not_promoted"]:
        remediation_codes.append("PHYSICAL_GATE_STATUS_PROMOTED")
    checks["hardware_evidence_unverified"] = conformance.get("hardware_evidence") == EXPECTED_HARDWARE_EVIDENCE
    if not checks["hardware_evidence_unverified"]:
        remediation_codes.append("HARDWARE_EVIDENCE_PROMOTED_WITHOUT_PROOF")
    checks["fixture_and_execution_boundary_locked"] = (
        conformance.get("fixture_only") is True
        and conformance.get("read_only") is True
        and conformance.get("external_submission_allowed") is False
        and conformance.get("external_transmission_performed") is False
        and conformance.get("runtime_mutation_performed") is False
        and conformance.get("authorization_promoted") is False
    )
    if not checks["fixture_and_execution_boundary_locked"]:
        remediation_codes.append("TRANSPORT_EXECUTION_BOUNDARY_MUTATED")
    checks["authorization_boundary_locked"] = conformance.get("authorization_boundary") == EXPECTED_BOUNDARY
    if not checks["authorization_boundary_locked"]:
        remediation_codes.append("TRANSPORT_AUTHORIZATION_BOUNDARY_MUTATED")
    serialized = json.dumps(
        {
            "decision": conformance.get("decision"),
            "transports": conformance.get("transports"),
            "normalized_by_transport": conformance.get("normalized_by_transport"),
            "failure_matrix": conformance.get("failure_matrix"),
        },
        sort_keys=True,
        ensure_ascii=True,
    ).lower()
    checks["conformance_evidence_redacted"] = not any(marker.lower() in serialized for marker in FORBIDDEN_MARKERS)
    if not checks["conformance_evidence_redacted"]:
        remediation_codes.append("TRANSPORT_CONFORMANCE_REDACTION_FAILED")

    remediation_codes = sorted(set(remediation_codes))
    decision = "P2_002_TRANSPORT_SELECTION_VERIFIED" if all(checks.values()) else "P2_002_TRANSPORT_SELECTION_BLOCKED"
    return {
        "schema_version": "p2-002-transport-selection-v1",
        "evidence_type": "P2_002_TRANSPORT_SELECTION",
        "decision": decision,
        "selected_software_transport": SELECTED_SOFTWARE_TRANSPORT,
        "candidate_transports": list(CANDIDATE_TRANSPORTS),
        "physical_gate_status": PHYSICAL_GATE_STATUS,
        "hardware_evidence": conformance.get("hardware_evidence"),
        "conformance_decision": conformance.get("decision"),
        "checks": checks,
        "remediation_codes": remediation_codes,
        "read_only": True,
        "fixture_only": True,
        "external_submission_allowed": False,
        "external_transmission_performed": False,
        "runtime_mutation_performed": False,
        "authorization_promoted": False,
        "external_authority": "NONE",
        "runtime_authority": "NONE",
        "clinical_validation": "PENDING",
        "production_ready": False,
        "claim_boundary": "CONTROLLED_PRODUCTION_PROTOTYPE",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate_transport_selection(), ensure_ascii=True, indent=2, sort_keys=True))
