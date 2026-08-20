from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from external_anchor import AnchorReceipt, ExternalAnchorAdapter, ExternalAnchorError, MemoryAppendOnlyAnchor
from his_admission_gateway_contract import GatewayTokenError, SandboxAdmissionGateway
from wave2_integration_forensic_readiness import LOCKED_AUTHORIZATION, template, validate_wave2_manifest


def expect_error(action, fragment: str) -> None:
    try:
        action()
    except Exception as exc:
        assert fragment in str(exc), (str(exc), fragment)
    else:
        raise AssertionError(f"expected failure containing {fragment!r}")


def run() -> None:
    base = template()
    assert validate_wave2_manifest(base, template_only=True)["valid"] is True
    print("[WAVE2 ADV] Blank-safe GV-03/GV-07 manifest: PASSED")

    mutated = template()
    mutated["unexpected"] = True
    expect_error(lambda: validate_wave2_manifest(mutated, template_only=True), "unknown fields")
    nested = template()
    nested["common_controls"]["unexpected"] = True
    expect_error(lambda: validate_wave2_manifest(nested, template_only=True), "unknown common_controls fields")
    track_nested = template()
    track_nested["tracks"]["GV-03"]["unexpected"] = True
    expect_error(lambda: validate_wave2_manifest(track_nested, template_only=True), "unknown GV-03 fields")
    print("[WAVE2 ADV] Top-level/nested allowlists: PASSED")

    for field, value, fragment in (
        ("status", "EXTERNAL_INTEGRATION_READY", "status must remain"),
        ("execution_status", "STARTED", "execution_status must remain"),
        ("external_integration", "VERIFIED", "external_integration must remain"),
        ("clinical_validation", "AUTHORIZED", "clinical_validation must remain"),
    ):
        payload = template()
        payload[field] = value
        expect_error(lambda payload=payload: validate_wave2_manifest(payload, template_only=True), fragment)
    escalation = template()
    escalation["authorization_boundary"] = {**LOCKED_AUTHORIZATION, "production_authorized": True}
    expect_error(lambda: validate_wave2_manifest(escalation, template_only=True), "authorization boundary must remain locked")
    print("[WAVE2 ADV] Status/authorization escalation refusal: PASSED")

    unsafe = template()
    unsafe["common_controls"]["scope_ref"] = "opaque:scope@example.invalid"
    expect_error(lambda: validate_wave2_manifest(unsafe, template_only=True), "opaque reference")
    unsafe = template()
    unsafe["common_controls"]["stop_rule"] = "Bearer abc123"
    expect_error(lambda: validate_wave2_manifest(unsafe, template_only=True), "secret material")
    unsafe = template()
    unsafe["tracks"]["GV-03"]["stop_conditions"][0] = "HN-2026-1234 crosses boundary"
    expect_error(lambda: validate_wave2_manifest(unsafe, template_only=True), "raw identity/contact")
    print("[WAVE2 ADV] Raw identity/contact and secret rejection: PASSED")

    gateway = SandboxAdmissionGateway()
    raw_reference = "HN-2026-8901"
    token = gateway.issue(raw_reference, ttl_seconds=30)
    assert token.startswith("ptok-")
    assert raw_reference not in repr(gateway._records)
    payload = gateway.hub_admission_payload(token, bed_no="W04-B12", idempotency_key="handoff-opaque-001")
    assert payload["patient_token"] == token
    assert raw_reference not in repr(payload)
    gateway.revoke(token)
    expect_error(lambda: gateway.validate(token), "revoked_token")
    expired_gateway = SandboxAdmissionGateway(clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    expired_token = expired_gateway.issue("AN-123", ttl_seconds=1)
    expired_gateway._clock = lambda: datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
    expect_error(lambda: expired_gateway.validate(expired_token), "expired_token")
    print("[WAVE2 ADV] GV-03 opaque token, revocation and expiry boundary: PASSED")

    provider = MemoryAppendOnlyAnchor()
    adapter = ExternalAnchorAdapter(provider, provider_id=provider.provider_id)
    block_hash = "a" * 64
    chain_tip = "b" * 64
    receipt = adapter.anchor_with_receipt(block_hash=block_hash, chain_tip=chain_tip, package_id=7)
    assert adapter.verify_receipt(receipt) is True
    assert receipt.evidence_class == "EXTERNAL_PROVIDER_RECEIPT_UNVERIFIED"
    assert adapter.anchor(block_hash=block_hash, chain_tip=chain_tip, package_id=7) is True
    assert len(provider.snapshot()) == 1
    tampered = replace(receipt, block_hash="c" * 64)
    assert adapter.verify_receipt(tampered) is False
    expect_error(lambda: adapter._validate_receipt(receipt, tampered), "receipt_hash_mismatch")
    local_claim = template()["common_controls"]["local_anchor_claim"]
    assert local_claim == "LOCAL_TAMPER_EVIDENT_ONLY_NOT_EXTERNAL_WORM"
    print("[WAVE2 ADV] GV-07 receipt binding, replay, tamper and claim boundary: PASSED")

    print("WAVE2_INTEGRATION_FORENSIC_HARDENING_PASSED")


if __name__ == "__main__":
    run()
