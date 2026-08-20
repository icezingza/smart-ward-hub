from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from external_anchor import AnchorReceipt, AnchorRequest, ExternalAnchorAdapter, ExternalAnchorError, MemoryAppendOnlyAnchor
from p1_004_external_anchor_readiness import ExternalAnchorReadinessError, template, validate_anchor_manifest

ROOT = Path(__file__).resolve().parent
BLOCK = "1" * 64
CHAIN = "2" * 64
TEMPLATE_PATH = ROOT / "evals/micro_rag/evidence/p1-004-external-anchor-readiness-template-20260820.json"
SCHEMA_PATH = ROOT / "evals/micro_rag/evidence/p1-004-external-anchor-readiness-schema-v1.json"


def expect_error(action, expected: str) -> None:
    try:
        action()
    except ExternalAnchorError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def expect_manifest_rejection(payload: dict, fragment: str) -> None:
    try:
        validate_anchor_manifest(payload, template_only=True)
    except ExternalAnchorReadinessError as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError("manifest mutation was accepted")


class OutageClient(MemoryAppendOnlyAnchor):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode

    def publish(self, request: AnchorRequest):
        if self.mode == "publish-outage":
            raise RuntimeError("provider unavailable")
        return super().publish(request)

    def verify(self, receipt: AnchorReceipt) -> bool:
        if self.mode == "verify-outage":
            raise RuntimeError("verification unavailable")
        if self.mode == "verify-false":
            return False
        return super().verify(receipt)


class ReceiptMutationClient(MemoryAppendOnlyAnchor):
    def __init__(self, field: str) -> None:
        super().__init__()
        self.field = field

    def publish(self, request: AnchorRequest):
        receipt = super().publish(request)
        if self.field == "anchor_id":
            return replace(receipt, anchor_id="")
        if self.field == "timestamp":
            return replace(receipt, accepted_at_utc="not-a-time")
        if self.field == "provider":
            return replace(receipt, provider_id="wrong-provider")
        return receipt


def test_readiness_manifest_mutations() -> None:
    assert validate_anchor_manifest(template(), template_only=True)["valid"] is True
    payload = template()
    payload["unexpected"] = True
    expect_manifest_rejection(payload, "unknown fields")

    payload = template()
    payload["authorization_boundary"]["production_authorized"] = True
    expect_manifest_rejection(payload, "authorization boundary must remain locked")

    payload = template()
    payload["tracks"].pop("AC-005")
    expect_manifest_rejection(payload, "tracks must contain exactly")

    payload = template()
    payload["external_worm_verified"] = True
    expect_manifest_rejection(payload, "external_worm_verified must remain false")

    payload = template()
    payload["common_controls"]["stop_rule"] = "Use provider@example.invalid"
    expect_manifest_rejection(payload, "must not contain raw identity/contact")

    assert json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))["status"] == "EXTERNAL_ANCHOR_SOFTWARE_PREPARATION_READY"
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["$id"].endswith("p1-004-external-anchor-readiness-v1")
    print("[P1-004] Readiness manifest and claim-boundary mutations: PASSED")


def test_provider_lifecycle_adversarial() -> None:
    provider = MemoryAppendOnlyAnchor()
    adapter = ExternalAnchorAdapter(provider, provider_id=provider.provider_id)
    first = adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=11)
    replay = adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=11)
    assert first == replay
    assert len(provider.snapshot()) == 1
    assert adapter.verify_receipt(first) is True
    print("[P1-004] Idempotent replay and provider readback: PASSED")

    expect_error(lambda: provider.delete(first.idempotency_key), "append_only_delete_forbidden")
    provider.tamper_for_test(first.idempotency_key, block_hash="3" * 64)
    assert adapter.verify_receipt(first) is False
    print("[P1-004] Delete refusal and receipt tamper detection: PASSED")

    for field in ("anchor_id", "timestamp", "provider"):
        client = ReceiptMutationClient(field)
        mutation_adapter = ExternalAnchorAdapter(client, provider_id=client.provider_id)
        expected = "receipt_provider_mismatch" if field == "provider" else "invalid_external_receipt"
        expect_error(lambda mutation_adapter=mutation_adapter: mutation_adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=12), expected)
    print("[P1-004] Anchor-id/timestamp/provider receipt mutations fail closed: PASSED")

    publish_outage = OutageClient("publish-outage")
    outage_adapter = ExternalAnchorAdapter(publish_outage, provider_id=publish_outage.provider_id)
    expect_error(lambda: outage_adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=13), "external_anchor_publish_failed")

    for mode in ("verify-outage", "verify-false"):
        client = OutageClient(mode)
        outage_adapter = ExternalAnchorAdapter(client, provider_id=client.provider_id)
        expect_error(lambda outage_adapter=outage_adapter: outage_adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=14), "external_receipt_verification_failed")
    print("[P1-004] Publish/verify outage and false verification fail closed: PASSED")


def test_request_type_and_boundary_adversarial() -> None:
    provider = MemoryAppendOnlyAnchor()
    expect_error(lambda: ExternalAnchorAdapter(None, provider_id="local"), "independent_provider_id_required")
    expect_error(lambda: ExternalAnchorAdapter(None, provider_id=""), "independent_provider_id_required")
    adapter = ExternalAnchorAdapter(provider, provider_id=provider.provider_id)
    expect_error(lambda: adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=True), "invalid_package_id")
    expect_error(lambda: adapter.anchor_with_receipt(block_hash="A" * 64, chain_tip=CHAIN, package_id=1), "invalid_block_hash")
    expect_error(lambda: adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN + "x", package_id=1), "invalid_chain_tip")
    assert adapter.verify_receipt(None) is False
    print("[P1-004] Provider identity, type confusion and digest boundary checks: PASSED")


if __name__ == "__main__":
    test_readiness_manifest_mutations()
    test_provider_lifecycle_adversarial()
    test_request_type_and_boundary_adversarial()
    print("P1_004_EXTERNAL_ANCHOR_HARDENING_TESTS_PASSED")
