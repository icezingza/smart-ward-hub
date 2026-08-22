"""Focused/adversarial tests for the P2-002 transport selection gate."""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

from p2_002_adapter_conformance import check_conformance
from p2_002_transport_selection import evaluate_transport_selection


def test_serial_is_verified_first_software_profile():
    report = evaluate_transport_selection()
    assert report["decision"] == "P2_002_TRANSPORT_SELECTION_VERIFIED"
    assert report["selected_software_transport"] == "serial"
    assert report["candidate_transports"] == ["mqtt", "websocket", "serial", "ble"]
    assert report["physical_gate_status"] == "NOT_STARTED"
    assert report["hardware_evidence"] == "UNVERIFIED"
    assert report["remediation_codes"] == []
    assert all(report["checks"].values())
    assert report["production_ready"] is False
    print("[P2-002 Selection] Serial is the verified first software profile: PASSED")


def test_conformance_blocker_prevents_transport_selection():
    conformance = deepcopy(check_conformance())
    conformance["decision"] = "P2_002_ADAPTER_CONFORMANCE_BLOCKED"
    with patch("p2_002_transport_selection.check_conformance", return_value=conformance):
        report = evaluate_transport_selection()
    assert report["decision"] == "P2_002_TRANSPORT_SELECTION_BLOCKED"
    assert report["checks"]["conformance_decision_verified"] is False
    assert "ADAPTER_CONFORMANCE_NOT_VERIFIED" in report["remediation_codes"]
    print("[P2-002 Selection] Conformance blocker prevents selection: PASSED")


def test_selection_and_physical_gate_mutations_fail_closed():
    with patch("p2_002_transport_selection.SELECTED_SOFTWARE_TRANSPORT", "mqtt"), patch(
        "p2_002_transport_selection.PHYSICAL_GATE_STATUS", "PASSED"
    ):
        report = evaluate_transport_selection()
    assert report["decision"] == "P2_002_TRANSPORT_SELECTION_BLOCKED"
    assert report["checks"]["serial_selected_as_first_profile"] is False
    assert report["checks"]["hardware_gate_not_promoted"] is False
    assert "FIRST_TRANSPORT_SELECTION_CHANGED" in report["remediation_codes"]
    assert "PHYSICAL_GATE_STATUS_PROMOTED" in report["remediation_codes"]
    print("[P2-002 Selection] Transport/physical gate mutations fail closed: PASSED")


def test_candidate_matrix_mutation_fails_closed():
    conformance = deepcopy(check_conformance())
    conformance["transports"] = ["mqtt", "websocket", "ble"]
    with patch("p2_002_transport_selection.check_conformance", return_value=conformance):
        report = evaluate_transport_selection()
    assert report["decision"] == "P2_002_TRANSPORT_SELECTION_BLOCKED"
    assert report["checks"]["all_candidates_conform"] is False
    assert report["checks"]["selected_transport_in_conformance"] is False
    assert "TRANSPORT_CONFORMANCE_MATRIX_INCOMPLETE" in report["remediation_codes"]
    assert "SELECTED_TRANSPORT_NOT_CONFORMANCE_TESTED" in report["remediation_codes"]
    print("[P2-002 Selection] Candidate conformance matrix mutation fails closed: PASSED")


def test_execution_and_authorization_boundary_mutations_fail_closed():
    conformance = deepcopy(check_conformance())
    conformance["fixture_only"] = False
    conformance["authorization_boundary"]["production_authorized"] = True
    with patch("p2_002_transport_selection.check_conformance", return_value=conformance):
        report = evaluate_transport_selection()
    assert report["decision"] == "P2_002_TRANSPORT_SELECTION_BLOCKED"
    assert report["checks"]["fixture_and_execution_boundary_locked"] is False
    assert report["checks"]["authorization_boundary_locked"] is False
    assert "TRANSPORT_EXECUTION_BOUNDARY_MUTATED" in report["remediation_codes"]
    assert "TRANSPORT_AUTHORIZATION_BOUNDARY_MUTATED" in report["remediation_codes"]
    assert report["authorization_promoted"] is False
    print("[P2-002 Selection] Execution/authorization mutations cannot self-promote: PASSED")


def test_redaction_mutation_fails_closed():
    conformance = deepcopy(check_conformance())
    conformance["normalized_by_transport"]["serial"]["patient_token"] = "forbidden-fixture-value"
    with patch("p2_002_transport_selection.check_conformance", return_value=conformance):
        report = evaluate_transport_selection()
    assert report["decision"] == "P2_002_TRANSPORT_SELECTION_BLOCKED"
    assert report["checks"]["conformance_evidence_redacted"] is False
    assert "TRANSPORT_CONFORMANCE_REDACTION_FAILED" in report["remediation_codes"]
    print("[P2-002 Selection] Redaction mutation fails closed: PASSED")


def run() -> None:
    tests = [
        test_serial_is_verified_first_software_profile,
        test_conformance_blocker_prevents_transport_selection,
        test_selection_and_physical_gate_mutations_fail_closed,
        test_candidate_matrix_mutation_fails_closed,
        test_execution_and_authorization_boundary_mutations_fail_closed,
        test_redaction_mutation_fails_closed,
    ]
    for test in tests:
        test()
    print(f"[P2-002 Selection] focused/adversarial tests: {len(tests)} PASSED")
    print("P2_002_TRANSPORT_SELECTION_TESTS_PASSED")


if __name__ == "__main__":
    run()
