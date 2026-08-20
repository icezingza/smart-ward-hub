from __future__ import annotations

from production_readiness_audit import build_report


def main() -> int:
    report = build_report()
    assert report["overall_decision"] == "NOT_PRODUCTION_READY"
    assert report["authorization"]["external_authority"] == "NONE"
    assert report["authorization"]["clinical_validation_authorized"] is False
    assert report["authorization"]["production_authorized"] is False
    assert report["authorization"]["runtime_authority"] == "NONE"
    assert report["authorization"]["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert report["status_counts"]["Implemented"] >= 1
    assert report["status_counts"]["Unverified"] >= 1
    assert report["status_counts"]["Experimental"] >= 1
    areas = {item["area"] for item in report["findings"]}
    for required in {"host_hardening", "hardware", "identity_transport", "clinical_governance", "external_gates", "forensic_anchor", "production_claim"}:
        assert required in areas
    print("PRODUCTION_READINESS_AUDIT_TESTS_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
