from __future__ import annotations

import json

from external_anchor import (
    AnchorReceipt,
    ExternalAnchorAdapter,
    ExternalAnchorError,
    MemoryAppendOnlyAnchor,
)


BLOCK = "a" * 64
CHAIN = "b" * 64


def expect_error(action, expected: str) -> None:
    try:
        action()
    except ExternalAnchorError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


def run() -> None:
    provider = MemoryAppendOnlyAnchor()
    adapter = ExternalAnchorAdapter(provider, provider_id=provider.provider_id)
    receipt = adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=7)
    assert receipt.status == "ACCEPTED"
    assert receipt.evidence_class == "EXTERNAL_PROVIDER_RECEIPT_UNVERIFIED"
    assert adapter.verify_receipt(receipt) is True
    print("[P1-004] Accepted receipt identity and verification: PASSED")

    replay = adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=7)
    assert replay == receipt
    assert len(provider.snapshot()) == 1
    print("[P1-004] Idempotent replay does not create duplicate anchor: PASSED")

    expect_error(lambda: provider.delete(receipt.idempotency_key), "append_only_delete_forbidden")
    print("[P1-004] Append-only delete refusal: PASSED")

    provider.tamper_for_test(receipt.idempotency_key, block_hash="c" * 64)
    assert adapter.verify_receipt(receipt) is False
    print("[P1-004] Tampered provider record fails receipt verification: PASSED")

    expect_error(
        lambda: adapter.anchor_with_receipt(block_hash="not-a-hash", chain_tip=CHAIN, package_id=8),
        "invalid_block_hash",
    )
    expect_error(
        lambda: adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=0),
        "invalid_package_id",
    )
    expect_error(
        lambda: ExternalAnchorAdapter(None, provider_id="local"),
        "independent_provider_id_required",
    )
    expect_error(
        lambda: ExternalAnchorAdapter(None, provider_id="hospital-worm" ).anchor_with_receipt(
            block_hash=BLOCK, chain_tip=CHAIN, package_id=9
        ),
        "external_anchor_client_unconfigured",
    )
    print("[P1-004] Invalid request and unconfigured external client fail closed: PASSED")

    class WrongReceiptClient(MemoryAppendOnlyAnchor):
        def publish(self, request):
            base = super().publish(request)
            return AnchorReceipt(
                provider_id=base.provider_id,
                anchor_id=base.anchor_id,
                idempotency_key=base.idempotency_key,
                package_id=base.package_id + 1,
                block_hash=base.block_hash,
                chain_tip=base.chain_tip,
                accepted_at_utc=base.accepted_at_utc,
                status=base.status,
                evidence_class=base.evidence_class,
            )

    wrong = WrongReceiptClient()
    wrong_adapter = ExternalAnchorAdapter(wrong, provider_id=wrong.provider_id)
    expect_error(
        lambda: wrong_adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=10),
        "receipt_package_mismatch",
    )
    print("[P1-004] Mismatched external receipt is rejected before acceptance: PASSED")

    serialized = json.dumps(provider.snapshot(), ensure_ascii=True)
    assert "patient_token" not in serialized
    assert "private_key" not in serialized
    print("[P1-004] Anchor snapshot contains neither patient identity nor private-key material: PASSED")
    print("EXTERNAL_ANCHOR_CONTRACT_TESTS_PASSED")


if __name__ == "__main__":
    run()
