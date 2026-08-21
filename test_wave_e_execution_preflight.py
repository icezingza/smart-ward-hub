from __future__ import annotations

from dataclasses import replace
import json

from wave_e_execution_preflight import (
    CRITERIA,
    EntryCriterion,
    WaveEPreflightError,
    build_empty_preflight,
)


def expect_error(callback) -> None:
    try:
        callback()
    except WaveEPreflightError:
        return
    raise AssertionError("expected WaveEPreflightError")


def run() -> None:
    preflight = build_empty_preflight(package_revision="wave-e-preflight-20260821", source_revision="fixture-revision-001")
    summary = preflight.validate_and_summarize()
    assert summary["coordination_state"] == "READY_FOR_EXTERNAL_OWNER_APPOINTMENT"
    assert summary["execution_permitted"] is False
    assert summary["external_validation_started"] is False
    assert summary["missing_criteria"] == list(CRITERIA)
    assert summary["authorization_snapshot"]["external_authority"] == "NONE"
    packet = preflight.export_handoff_packet()
    assert packet["packet_status"] == "READY_FOR_EXTERNAL_OWNER_APPOINTMENT"
    assert len(packet["package_hash"]) == 64
    print("[Wave E Preflight] Empty owner-appointment packet remains fail-closed: PASSED")

    asserted = tuple(
        EntryCriterion(
            criterion_id=criterion_id,
            asserted=True,
            evidence_ref=f"owner://evidence/{criterion_id.lower()}",
            owner_role="external_service_owner",
        )
        for criterion_id in CRITERIA
    )
    complete = replace(preflight, criteria=asserted)
    assert complete.external_execution_preconditions_present is True
    assert complete.validate_and_summarize()["missing_criteria"] == []
    assert complete.validate_and_summarize()["execution_permitted"] is False
    print("[Wave E Preflight] Exact E-01..E-10 coverage never self-authorizes execution: PASSED")

    expect_error(lambda: replace(preflight, execution_permitted=True).validate())
    expect_error(
        lambda: replace(
            preflight,
            authorization_snapshot={
                "external_authority": "AUTHORIZED_BY_EXTERNAL_OWNER",
                "clinical_validation_authorized": False,
                "production_authorized": False,
                "runtime_authority": "NONE",
                "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
            },
        ).validate()
    )
    expect_error(lambda: replace(preflight, external_owner_role=preflight.independent_verifier_role).validate())
    expect_error(lambda: replace(preflight, criteria=preflight.criteria[:-1]).validate())
    expect_error(lambda: replace(preflight, criteria=preflight.criteria[:-1] + (EntryCriterion("E-01", False, None, "external_service_owner"),)).validate())
    expect_error(lambda: replace(preflight, source_revision="Bearer secret").validate())
    print("[Wave E Preflight] Authorization mutation, role collision, coverage drift and unsafe refs reject: PASSED")

    tampered = json.loads(json.dumps(packet))
    tampered["preflight"]["execution_permitted"] = True
    assert tampered["preflight"]["execution_permitted"] is True
    assert packet["preflight"]["execution_permitted"] is False
    print("[Wave E Preflight] Exported packet is independent snapshot and remains no-authorization: PASSED")
    print("WAVE_E_EXECUTION_PREFLIGHT_TESTS_PASSED")


if __name__ == "__main__":
    run()
