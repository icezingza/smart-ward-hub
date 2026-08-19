from __future__ import annotations

from dataclasses import replace

from external_anchor import AnchorReceipt, ExternalAnchorAdapter, ExternalAnchorError, MemoryAppendOnlyAnchor


BLOCK = "1" * 64
CHAIN = "2" * 64


def expect_error(action, expected: str) -> None:
    try:
        action()
    except ExternalAnchorError as exc:
        assert str(exc) == expected, (str(exc), expected)
    else:
        raise AssertionError(f"expected {expected}")


class MutatingClient(MemoryAppendOnlyAnchor):
    def __init__(self, mutation: str) -> None:
        super().__init__()
        self.mutation = mutation

    def publish(self, request):
        receipt = super().publish(request)
        if self.mutation == "status":
            return replace(receipt, status="REJECTED")
        if self.mutation == "provider":
            return replace(receipt, provider_id="wrong-provider")
        if self.mutation == "idempotency":
            return replace(receipt, idempotency_key="0" * 64)
        if self.mutation == "chain":
            return replace(receipt, chain_tip="3" * 64)
        if self.mutation == "evidence":
            return replace(receipt, evidence_class="EXTERNAL_WORM_VERIFIED")
        if self.mutation == "type":
            return {"not": "a receipt"}
        return receipt


def run() -> None:
    for mutation, expected in (
        ("status", "external_anchor_not_accepted"),
        ("provider", "receipt_provider_mismatch"),
        ("idempotency", "receipt_idempotency_mismatch"),
        ("chain", "receipt_hash_mismatch"),
        ("evidence", "receipt_evidence_class_invalid"),
        ("type", "invalid_external_receipt"),
    ):
        client = MutatingClient(mutation)
        adapter = ExternalAnchorAdapter(client, provider_id=client.provider_id)
        expect_error(
            lambda adapter=adapter: adapter.anchor_with_receipt(block_hash=BLOCK, chain_tip=CHAIN, package_id=11),
            expected,
        )
    print("[P1-004] Receipt fault matrix rejects status/provider/idempotency/hash/evidence/type mutations: PASSED")

    expect_error(
        lambda: ExternalAnchorAdapter(MemoryAppendOnlyAnchor(), provider_id="different-provider"),
        "client_provider_id_mismatch",
    )
    print("[P1-004] Client/provider identity mismatch fails closed: PASSED")
    print("EXTERNAL_ANCHOR_FAULT_INJECTION_TESTS_PASSED")


if __name__ == "__main__":
    run()
