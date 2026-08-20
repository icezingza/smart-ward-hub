from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from pydantic import ValidationError

from external_authorization_api_wave_e_evidence import (
    DossierState,
    DossierStateMachine,
    EvidenceStatus,
    FailureClass,
    SignatureVerificationResult,
    TimeVerificationResult,
    WaveEEvidenceRecord,
)


NOW = datetime(2026, 8, 20, 3, 0, tzinfo=timezone.utc)
HASH = "a" * 64


def valid_record(**overrides):
    payload = {
        "test_run_id": "wave-e-run-001",
        "test_case_id": "T-09",
        "status": EvidenceStatus.READY_FOR_INDEPENDENT_REVIEW,
        "expected_result": "untrusted response remains blocked",
        "actual_result": "signature verified and independent read-back available",
        "failure_class": FailureClass.NONE,
        "started_at_utc": NOW,
        "observed_at_utc": NOW + timedelta(seconds=1),
        "completed_at_utc": NOW + timedelta(seconds=2),
        "clock_source": "approved-test-reference-clock",
        "clock_skew_ms": 2,
        "time_verification_result": TimeVerificationResult.PASS,
        "endpoint_environment_id": "external-auth-nonprod-01",
        "endpoint_identity_ref": "tls://endpoint-ref-001",
        "tls_certificate_fingerprint": HASH,
        "identity_transport_ref": "mtls-transcript-001",
        "request_correlation_id": "corr-001",
        "idempotency_key_hash": HASH,
        "request_sha256": HASH,
        "response_sha256": HASH,
        "remote_receipt_id": "receipt-001",
        "reconciliation_result": "NOT_REQUIRED",
        "artifact_type": "signed-response-transcript",
        "artifact_sha256": HASH,
        "manifest_sha256": HASH,
        "artifact_size_bytes": 2048,
        "artifact_record_count": 1,
        "signature_ref": "sig-ref-001",
        "key_id": "external-test-key-001",
        "signature_algorithm": "Ed25519",
        "signed_payload_hash": HASH,
        "signature_verification_result": SignatureVerificationResult.PASS,
        "independent_readback_ref": "readback-001",
        "scope_id": "wave-e-scope-001",
        "window_id": "wave-e-window-001",
        "expiry": NOW + timedelta(hours=1),
        "revocation_status": "NOT_REVOKED",
        "stop_authority_ref": "stop-authority-001",
        "stop_trigger": "NONE",
        "topology": "SINGLE_PROCESS",
        "worker_count": 1,
        "limiter_backend": "process-local-test-limiter",
        "quota_scope": "single-test-process",
        "chain_of_custody_ref": "custody-001",
        "prepared_by_role": "evidence_custodian",
        "external_owner_role": "external_authorization_service_owner",
    }
    payload.update(overrides)
    return payload


def test_state_machine_and_boundary():
    state = DossierStateMachine()
    state = state.transition(
        DossierState.READY_FOR_EXTERNAL_OWNER_APPOINTMENT,
        actor_role="integration_owner",
        reason="schema amendment is ready for owner appointment",
    )
    state = state.transition(
        DossierState.READY_FOR_EXTERNAL_EXECUTION,
        actor_role="external_owner",
        reason="external prerequisites recorded",
    )
    state = state.transition(
        DossierState.IN_EXECUTION,
        actor_role="external_owner",
        reason="approved non-production test window opened",
    )
    state = state.transition(
        DossierState.READY_FOR_INDEPENDENT_REVIEW,
        actor_role="evidence_custodian",
        reason="all artifacts captured and hash-bound",
    )
    snapshot = state.model_dump_for_evidence()
    assert snapshot["state"] == "READY_FOR_INDEPENDENT_REVIEW"
    assert snapshot["external_authority"] == "NONE"
    assert snapshot["clinical_validation_authorized"] is False
    assert snapshot["production_authorized"] is False
    assert snapshot["runtime_authority"] == "NONE"
    assert snapshot["pilot_gate_status"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"

    blocked = state.transition(
        DossierState.BLOCKED,
        actor_role="stop_authority",
        reason="independent reviewer requested clarification",
    )
    reopened = blocked.transition(
        DossierState.READY_FOR_EXTERNAL_OWNER_APPOINTMENT,
        actor_role="integration_owner",
        reason="clarification recorded; explicit reopen",
    )
    assert reopened.revision == blocked.revision + 1


def test_invalid_state_transition_is_rejected():
    try:
        DossierStateMachine().transition(
            DossierState.IN_EXECUTION,
            actor_role="integration_owner",
            reason="invalid direct transition",
        )
    except ValueError as exc:
        assert "invalid dossier transition" in str(exc)
    else:
        raise AssertionError("invalid direct dossier transition was accepted")


def test_valid_review_ready_record():
    record = WaveEEvidenceRecord.model_validate(valid_record())
    assert record.schema_version == "wave-e-evidence-v1"
    assert record.test_case_id == "T-09"
    assert record.signature_verification_result is SignatureVerificationResult.PASS
    dumped = record.model_dump(mode="json")
    assert dumped["external_authority"] == "NONE"
    assert dumped["production_authorized"] is False
    assert dumped["raw_identity_present"] is False


def test_extra_field_and_naive_timestamp_are_rejected():
    with _expect_validation_error():
        WaveEEvidenceRecord.model_validate({**valid_record(), "unexpected": "reject"})
    with _expect_validation_error():
        WaveEEvidenceRecord.model_validate({**valid_record(), "started_at_utc": datetime(2026, 8, 20, 3, 0)})


def test_review_ready_requires_signature_receipt_and_response_hash():
    for field, value in (
        ("signature_verification_result", SignatureVerificationResult.BLOCKED),
        ("remote_receipt_id", None),
        ("response_sha256", None),
    ):
        with _expect_validation_error():
            WaveEEvidenceRecord.model_validate({**valid_record(), field: value})


def test_fail_closed_and_authorization_mutations_are_rejected():
    with _expect_validation_error():
        WaveEEvidenceRecord.model_validate({**valid_record(), "external_authority": "EXTERNAL_OWNER"})
    with _expect_validation_error():
        WaveEEvidenceRecord.model_validate(
            {
                **valid_record(),
                "status": EvidenceStatus.EXECUTED_BLOCKED,
                "failure_class": FailureClass.NONE,
            }
        )
    state = DossierStateMachine()
    try:
        state.external_authority = "EXTERNAL_OWNER"
    except ValidationError:
        pass
    else:
        raise AssertionError("authorization boundary mutation was accepted")


def test_exported_schema_matches_contract():
    schema_path = Path(__file__).resolve().parent / "evals/micro_rag/evidence/wave-e-evidence-schema-v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["schema_id"] == "wave-e-evidence-v1"
    case_pattern = schema["record_schema"]["properties"]["test_case_id"]["pattern"]
    assert "0[1-9]" in case_pattern and "1[0-2]" in case_pattern
    assert "READY_FOR_EXTERNAL_OWNER_APPOINTMENT" in schema["dossier_state_machine"]["states"]
    assert schema["authorization_boundary"]["external_authority"] == "NONE"
    assert schema["authorization_boundary"]["production_authorized"] is False


def test_commit_unknown_requires_reconciliation_and_topology_is_bounded():
    with _expect_validation_error():
        WaveEEvidenceRecord.model_validate(
            {
                **valid_record(),
                "status": EvidenceStatus.EXECUTED_BLOCKED,
                "failure_class": FailureClass.COMMIT_UNKNOWN,
                "reconciliation_result": "NOT_RECONCILED",
                "signature_verification_result": SignatureVerificationResult.BLOCKED,
                "remote_receipt_id": None,
                "response_sha256": None,
            }
        )
    with _expect_validation_error():
        WaveEEvidenceRecord.model_validate({**valid_record(), "topology": "SINGLE_PROCESS", "worker_count": 2})


class _expect_validation_error:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not ValidationError:
            raise AssertionError(f"expected ValidationError, got {exc_type}") from exc_value
        return True


if __name__ == "__main__":
    test_state_machine_and_boundary()
    test_invalid_state_transition_is_rejected()
    test_valid_review_ready_record()
    test_extra_field_and_naive_timestamp_are_rejected()
    test_review_ready_requires_signature_receipt_and_response_hash()
    test_fail_closed_and_authorization_mutations_are_rejected()
    test_exported_schema_matches_contract()
    test_commit_unknown_requires_reconciliation_and_topology_is_bounded()
    print("WAVE_E_EVIDENCE_SCHEMA_TESTS_PASSED")
