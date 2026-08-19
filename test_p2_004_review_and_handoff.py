from __future__ import annotations

from controlled_pilot_handoff import EXTERNAL_GATE_IDS, ControlledPilotHandoffError, build_controlled_pilot_handoff
from p2_004_review_decision import RepeatedSampleProtocol, ReviewDecisionError, decide_review_status


def summary(**overrides):
    payload = {
        "sample_count": 1,
        "total_case_results": 8,
        "provider_limited_cases": 0,
        "runtime_or_adapter_failures": 0,
        "quality_rejections": 0,
        "quality_denominator": 8,
        "quality_pass_rate": 1.0,
        "model_id": "fixture-model",
        "model_revision": "fixture-revision",
        "corpus_revision": "fixture-v2",
        "adapter_version": "response-adapter-v1",
        "retrieval_source": "document-registry-v2/rebuildable-index-v2",
        "registry_manifest_hash": "registry-hash",
        "index_hash": "index-hash",
    }
    payload.update(overrides)
    return payload


def gates(status: str = "OPEN"):
    return {gate_id: status for gate_id in EXTERNAL_GATE_IDS}


def run() -> None:
    blocked = decide_review_status(summary(), RepeatedSampleProtocol())
    assert blocked["status"] == "BLOCKED_INCOMPLETE_EVIDENCE"
    assert blocked["clinical_validation_authorized"] is False
    print("[P2-004 Review] One sample is blocked from external-review acceptance: PASSED")

    provider = decide_review_status(summary(sample_count=2, total_case_results=16, provider_limited_cases=1), RepeatedSampleProtocol())
    assert provider["status"] == "BLOCKED_PROVIDER_WINDOW"
    print("[P2-004 Review] Provider-limited repeated set remains blocked: PASSED")

    accepted = decide_review_status(summary(sample_count=2, total_case_results=16), RepeatedSampleProtocol())
    assert accepted["status"] == "ACCEPTED_FOR_EXTERNAL_REVIEW"
    print("[P2-004 Review] Compatible complete repeated set can be handed to external review: PASSED")

    handoff = build_controlled_pilot_handoff(
        handoff_id="p2004-review-handoff-001",
        review_decision=blocked,
        readiness_status="NOT_READY",
        gate_statuses=gates("OPEN"),
        evidence_refs=["P2_004_HARDENING_EVIDENCE.md"],
        blockers=["minimum compatible sample count not met", "runtime backend not externally verified"],
    )
    assert handoff.pilot_gate_status == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert handoff.clinical_validation_authorized is False
    assert handoff.production_authorized is False
    print("[P2-004 Handoff] NOT_READY package remains blocked and unauthorized: PASSED")

    blocked_gate_handoff = build_controlled_pilot_handoff(
        handoff_id="p2004-review-handoff-002",
        review_decision=accepted,
        readiness_status="READY_FOR_EXTERNAL_GOVERNANCE_REVIEW",
        gate_statuses={**gates("PASSED"), "GV-06": "BLOCKED"},
        evidence_refs=["P2_004_HARDENING_EVIDENCE.md"],
        blockers=["GV-06 external hardware evidence is blocked"],
    )
    assert blocked_gate_handoff.pilot_gate_status == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    print("[P2-004 Handoff] Blocked external gate cannot produce ready pilot gate: PASSED")

    try:
        RepeatedSampleProtocol(minimum_samples=1).validate()
    except ReviewDecisionError:
        print("[P2-004 Review] Protocol minimum sample guard is fail-closed: PASSED")
    else:
        raise AssertionError("invalid protocol was accepted")

    print("P2_004_REVIEW_AND_HANDOFF_TESTS_PASSED")


if __name__ == "__main__":
    run()
