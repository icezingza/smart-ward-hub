# Smart Ward Hub — Threat Model v0.1

**Status:** Engineering draft; requires security and clinical-owner review. This document is not a penetration-test report.

## Trust boundaries

| Boundary | Assets | Threats | Required controls |
|---|---|---|---|
| Device to Edge | Telemetry, device identity, sequence | spoofing, replay, malformed/oversized packet | Ed25519/device trust, sequence checks, bounded payload/framing |
| Edge API to operator | Alerts, bed/session state, commands | credential theft, privilege escalation, stale command | OIDC/scopes, revision checks, idempotency, audit, managed device identity |
| Edge storage | SQLite, checkpoint, audit, forensic anchor | theft, corruption, tampering, disk failure | least privilege, encryption/backup, WAL/recovery, integrity verification |
| Edge to HIS/Gateway | opaque tokens, handover acknowledgment | token mismatch, retry duplication, premature purge | gateway boundary, FHIR contract, explicit acknowledgment, reconciliation |
| Edge to external services | evidence receipt, identity/config | MITM, provider compromise, outage, false receipt | mTLS/TLS, receipt identity verification, fail closed, independent custody |
| Operator to workflow | reset, discharge, freeze, admission | unsafe action, wrong bed/session, alarm fatigue | state machine, confirmation gates, training, clinical stop rules |
| Build/release to runtime | source, dependencies, artifacts | vulnerable dependency, unreviewed change, secret leak | CI, SBOM, signed/provenance release, review, secret scan, rollback |

## High-priority abuse cases

1. Submit a valid-looking telemetry packet with a reused or out-of-order sequence.
2. Use a leaked static token to invoke pairing, reset, discharge, or handover actions.
3. Replay an admission or handover command after a timeout.
4. Inject a raw patient identifier into logs, checkpoints, audit records, or exports.
5. Modify a local forensic record and present it as an external immutable receipt.
6. Restore a stale or corrupted authorization/evidence snapshot as current state.
7. Exploit a multi-process deployment where process-local state diverges.
8. Deploy with demo/static credentials, wildcard hosts, public docs, or source-tree runtime paths.
9. Cause disk-full, power-loss, clock drift, network partition, or device replacement during an active session.
10. Misinterpret an alert as a diagnosis or use a stale alert to make a clinical decision.

## Required security evidence before pilot

Complete OIDC test-tenant validation, certificate rotation/revocation, threat-model review, dependency/SBOM scan, secrets scan, access-control review, backup encryption and restore drill, audit-retention test, incident-response tabletop, and an independent security review. Record residual risk, owner, expiry and stop condition for every item that remains open.
