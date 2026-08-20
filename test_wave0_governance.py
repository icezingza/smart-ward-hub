from __future__ import annotations

from datetime import datetime, timezone

from wave0_governance import (
    GovernanceState,
    GovernanceValidationError,
    SignedScope,
    TestWindow,
    build_synthetic_wave0_package,
)


NOW = datetime(2026, 8, 20, 8, 0, tzinfo=timezone.utc)


def manifest_entries():
    return [
        {
            "evidence_id": "wave0-software-001",
            "artifact_ref": "repo://run_all_tests.py",
            "evidence_class": "SOFTWARE_VERIFIED",
        },
        {
            "evidence_id": "wave0-blocker-001",
            "artifact_ref": "repo://CONTROLLED_PILOT_BLOCKER_ANALYSIS.md",
            "evidence_class": "BLOCKER_RECORD",
        },
    ]


def main() -> int:
    package = build_synthetic_wave0_package(NOW)
    prefreeze = package.validate(NOW)
    assert prefreeze["checks"]["local_ready_for_external_review"] is False
    assert prefreeze["checks"]["authorization_locked"] is True
    assert prefreeze["state"] == GovernanceState.READY_TO_FREEZE.value

    package.state = GovernanceState.READY_TO_FREEZE
    freeze = package.freeze_local(manifest_entries(), NOW)
    assert len(freeze.manifest_sha256) == 64
    assert freeze.external_authority == "NONE"
    assert freeze.external_verification_required is True

    report = package.validate(NOW)
    assert report["checks"]["local_ready_for_external_review"] is True
    assert report["state"] == GovernanceState.GOVERNANCE_PACKAGE_READY_FOR_EXTERNAL_REVIEW.value
    assert report["clinical_validation_authorized"] is False
    assert report["production_authorized"] is False
    assert report["runtime_authority"] == "NONE"

    try:
        package.freeze_local(manifest_entries(), NOW, reason="attempted silent mutation")
    except GovernanceValidationError:
        pass
    else:
        raise AssertionError("second freeze must fail closed")

    package.scope = SignedScope(
        scope_id="scope-bad",
        purpose="contains HN-1234",
        in_scope=("synthetic",),
        out_of_scope=("real patient care",),
        environment="isolated",
        test_window_ref="window",
        rollback_plan_ref="rollback",
        stop_criteria_ref="stop",
        expiry=NOW.replace(year=2027),
        signed_by_external_role="independent_reviewer",
        signature_ref="pending",
    )
    try:
        package.scope.validate(NOW)
    except GovernanceValidationError:
        pass
    else:
        raise AssertionError("raw identity in scope must be rejected")

    print("WAVE0_GOVERNANCE_TESTS_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
