# P1-004 External Forensic Anchor Readiness Report

**Decision:** `EXTERNAL_ANCHOR_SOFTWARE_PREPARATION_READY`
**Anchor execution:** `NOT_STARTED`
**Independent provider validation:** `UNVERIFIED`
**External WORM verified:** `false`
**Product status:** `NOT_PRODUCTION_READY`

## Scope

This package hardens the software adapter boundary for an independently operated forensic anchor provider. The local `MemoryAppendOnlyAnchor` is a deterministic provider stub. It is not an independent WORM service, trusted-time source, legal-retention system, access-control boundary or production durability layer.

## Prepared tracks

| Track | Software preparation | External evidence still required |
|---|---|---|
| AC-001 | Explicit non-local provider identity and client/provider binding | Service ownership and independent provider identity |
| AC-002 | Package/block/chain/receipt field matching | Redacted cross-boundary request/receipt transcript |
| AC-003 | Deterministic idempotency and single-receipt replay | Duplicate/replay behavior on real provider |
| AC-004 | Delete refusal in software stub | Independent append-only/WORM immutability and retention |
| AC-005 | Receipt verification required before success | Independent read-back from a second trust boundary |
| AC-006 | Rejected/mutated/malformed receipt and outage fail-closed behavior | Authenticated transport, retry/outage policy and service monitoring |
| AC-007 | Explicit claim that local evidence is only tamper-evident within Edge boundary | Trusted time, custody, retention/legal hold and independent review |

## Hardening changes

The adapter now rejects non-string or local provider IDs, wraps provider publish exceptions as `external_anchor_publish_failed`, treats verification exceptions/false values as `external_receipt_verification_failed`, validates receipt anchor identity and timezone-aware timestamp, and revalidates receipt/request binding in `verify_receipt`. The readiness manifest keeps `external_worm_verified=false`, `anchor_execution=NOT_STARTED`, `independent_provider_validation=UNVERIFIED` and the no-authorization boundary locked.

## Verification

The existing contract/fault tests plus the adversarial suite cover idempotent replay, duplicate prevention, delete refusal, provider-record tamper, provider/status/hash/evidence/type/anchor/timestamp mutations, publish/verify outage, false verification, provider identity mismatch, type confusion and digest boundary. The phase-end gate also validates the blank-safe template/schema, scans for private-key blocks and runs `git diff --check`.

All results are **software verification**. They must remain labeled `EXTERNAL_PROVIDER_RECEIPT_UNVERIFIED` and must not be presented as external immutable or tamper-proof evidence.

## Claim boundary

The valid local claim is **Tamper-Evident Evidence / external-anchor adapter software baseline**. This package does not support `tamper-proof`, `external WORM verified`, `trusted-time verified`, `clinical-ready`, `regulatory compliant` or `production-ready` claims.

The external gate remains blocked until Wave 0 owner appointment, signed scope/test window, independent provider ownership, authenticated transport, trusted time, retention/access policy, custody and cross-boundary read-back are supplied.
