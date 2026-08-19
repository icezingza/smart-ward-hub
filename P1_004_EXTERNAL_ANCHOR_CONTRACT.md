# Smart Ward Hub — P1-004 External Forensic Anchor Contract

**Status:** Software adapter contract and fault-injection baseline implemented; independent external service validation pending

## Boundary

The local `FileAnchorStore` remains a local append-only adapter with `anchor_type=local_append_only_adapter`. It can support **tamper-evident evidence within the Edge trust boundary**, but it must not be called external WORM, independent immutability or tamper-proof evidence.

`external_anchor.py` defines a separate adapter boundary for an independently operated provider. The adapter requires an explicit non-local provider identity, validates request and receipt identity, enforces a stable idempotency key, requires an accepted status and verifies the provider receipt before reporting success.

## Request and receipt contract

| Field | Requirement |
|---|---|
| `package_id` | Positive integer; scoped to the exact forensic package |
| `block_hash` | Lowercase SHA-256 hex digest in the current software contract |
| `chain_tip` | Lowercase SHA-256 hex digest for the chain tip |
| `idempotency_key` | SHA-256 of `package_id|block_hash|chain_tip` |
| `provider_id` | Independent provider identity; `local`, `filesystem` and `none` are rejected |
| `anchor_id` | Provider-issued receipt identity |
| `status` | Must be `ACCEPTED` |
| `evidence_class` | Current adapter expects `EXTERNAL_PROVIDER_RECEIPT_UNVERIFIED` until independent verification exists |

A receipt is accepted only when provider ID, package ID, block hash, chain tip, idempotency key, status and evidence class all match. A provider record that is later mutated fails verification. Replays return the original receipt and do not create a second record in the software stub.

## Software evidence

`MemoryAppendOnlyAnchor` is a deterministic provider stub used for contract tests. It demonstrates idempotency, deletion refusal, receipt verification and mutation detection. It does **not** provide an independent trust boundary, WORM guarantee, trusted timestamp, access control, legal retention or production durability.

The test suite also injects rejected status, wrong provider, wrong idempotency key, wrong chain tip, wrong evidence class, malformed receipt type and client/provider identity mismatch. All are rejected before the adapter reports success.

## External gates

To close P1-004, the project still needs an independently administered append-only/WORM service, authenticated transport, service identity, trusted timestamp, retention/legal hold policy, access control, monitoring, outage/retry behavior, receipt verification from a second trust boundary, key custody and a cross-boundary chain verification drill. The local stub and adapter tests must not be used to claim **tamper-proof**, **external immutable**, **regulatory compliant** or **production-ready** status.
