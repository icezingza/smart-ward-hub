"""Focused and adversarial tests for repository visibility governance."""

from __future__ import annotations

from copy import deepcopy

from repository_visibility_governance import (
    LOCKED_BOUNDARY,
    VisibilityCode,
    VisibilityDecision,
    evaluate_visibility,
)


BASE = {
    "repository": "icezingza/smart-ward-hub",
    "is_private": True,
    "default_branch": "main",
    "source": "GH_REPO_VIEW",
    "authorization_boundary": deepcopy(LOCKED_BOUNDARY),
    "external_submission_allowed": False,
    "authorization_promoted": False,
    "runtime_mutation_performed": False,
    "external_transmission_performed": False,
}


def _evaluate(**mutations):
    payload = deepcopy(BASE)
    for mutation in mutations.values():
        mutation(payload)
    return evaluate_visibility(payload)


def test_private_repository_is_confirmed():
    result = _evaluate()
    assert result.decision == VisibilityDecision.PRIVATE_REPOSITORY_CONFIRMED
    assert result.remediation_codes == ()
    assert all(result.checks.values())


def test_public_repository_blocks():
    result = _evaluate(public=lambda payload: payload.update(is_private=False))
    assert result.decision == VisibilityDecision.REPOSITORY_VISIBILITY_BLOCKED
    assert VisibilityCode.REPOSITORY_NOT_PRIVATE in result.remediation_codes


def test_repository_identity_mismatch_blocks():
    result = _evaluate(identity=lambda payload: payload.update(repository="other-owner/smart-ward-hub"))
    assert result.decision == VisibilityDecision.REPOSITORY_VISIBILITY_BLOCKED
    assert VisibilityCode.REPOSITORY_IDENTITY_MISMATCH in result.remediation_codes


def test_default_branch_mismatch_blocks():
    result = _evaluate(branch=lambda payload: payload.update(default_branch="develop"))
    assert result.decision == VisibilityDecision.REPOSITORY_VISIBILITY_BLOCKED
    assert VisibilityCode.DEFAULT_BRANCH_MISMATCH in result.remediation_codes


def test_untrusted_observation_source_blocks():
    result = _evaluate(source=lambda payload: payload.update(source="UNVERIFIED_CLAIM"))
    assert result.decision == VisibilityDecision.REPOSITORY_VISIBILITY_BLOCKED
    assert VisibilityCode.OBSERVATION_SOURCE_INVALID in result.remediation_codes


def test_boundary_mutation_blocks():
    result = _evaluate(boundary=lambda payload: payload["authorization_boundary"].update(production_authorized=True))
    assert result.decision == VisibilityDecision.REPOSITORY_VISIBILITY_BLOCKED
    assert VisibilityCode.AUTHORIZATION_BOUNDARY_MUTATED in result.remediation_codes


def test_execution_lock_mutation_blocks():
    result = _evaluate(execution=lambda payload: payload.update(external_submission_allowed=True))
    assert result.decision == VisibilityDecision.REPOSITORY_VISIBILITY_BLOCKED
    assert VisibilityCode.EXECUTION_BOUNDARY_MUTATED in result.remediation_codes


def test_missing_observation_blocks():
    result = evaluate_visibility(None)
    assert result.decision == VisibilityDecision.REPOSITORY_VISIBILITY_BLOCKED
    assert VisibilityCode.OBSERVATION_MISSING in result.remediation_codes


def test_input_is_not_mutated():
    payload = deepcopy(BASE)
    before = deepcopy(payload)
    result = evaluate_visibility(payload)
    assert result.decision == VisibilityDecision.PRIVATE_REPOSITORY_CONFIRMED
    assert payload == before


def test_public_status_is_not_authorization():
    result = _evaluate(public=lambda payload: payload.update(is_private=False))
    assert result.observation["is_private"] is False
    assert result.decision != VisibilityDecision.PRIVATE_REPOSITORY_CONFIRMED
    assert result.observation["authorization_boundary"] == LOCKED_BOUNDARY


def run() -> None:
    tests = [
        value for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(f"[Visibility] focused/adversarial tests: {len(tests)} PASSED")
    print("REPOSITORY_VISIBILITY_GOVERNANCE_TESTS_PASSED")


if __name__ == "__main__":
    run()
