# Wave 1 Technical Validation Package

**Release candidate source revision:** `58f8d60200ebe4bdbe0f87ed68965adefefc7a10`  
**Freeze manifest publication:** `67881520b2dfd05ba13f3f3b768ffb86c84c18bc`  
**Execution status:** `NOT_STARTED`  
**Environment:** isolated non-production only  
**Authorization boundary:** `external_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false`, `runtime_authority=NONE`

> Package นี้เป็น test-preparation contract สำหรับ Wave 1 ไม่ใช่คำสั่งให้เชื่อม production, real HIS, real patient/device หรือ real clinical workflow โดยอัตโนมัติ

## 1. Scope and ownership

| Track | Gate | Owner role | Required external participant | Current state |
|---|---|---|---|---|
| Identity transport | GV-04 | `security_owner` | IdP/certificate owner and network owner | `OWNER_APPOINTMENT_PENDING` |
| Device trust/key custody | GV-08 | `security_owner` | OEM/manufacturer or approved custody/HSM owner | `OWNER_APPOINTMENT_PENDING` |
| Acer/serial/power recovery | GV-06 | `reliability_owner` | Acer host operator and independent bench witness | `OWNER_APPOINTMENT_PENDING` |

Each track requires a separate test window, allowlist, stop authority, rollback reference and redacted evidence record. The same person must not silently act as preparer, stop authority, recovery approver and independent verifier.

## 2. GV-04 — OIDC and mTLS validation package

### Preconditions

The external owner must provide an isolated non-production issuer/tenant, discovery and JWKS URLs, audience, test identities, client registration, certificate chain, rotation/revocation procedure, approved DNS/network path and a rollback contact. No production token, private key or patient identity may be copied into the repository or evidence directory.

### Test matrix

| ID | Test | Required evidence | Stop condition |
|---|---|---|---|
| ID-001 | OIDC discovery/JWKS | redacted response hash, issuer, JWKS key IDs, timestamp | issuer/host mismatch or untrusted TLS |
| ID-002 | Claims/audience | redacted token claims hash, accepted/rejected scopes | wrong issuer/audience/role is accepted |
| ID-003 | Expiry/revocation | expired/revoked token rejection transcript | stale token continues to authorize |
| ID-004 | mTLS handshake | client/server cert fingerprints, chain, protocol and hostname verification | chain/hostname/clock failure |
| ID-005 | Certificate rotation | before/after key IDs, overlap/retirement and rollback transcript | old/revoked cert remains accepted outside policy |
| ID-006 | Network segmentation | approved source/destination/port ACL and deny transcript | endpoint reachable outside allowlist |
| ID-007 | Failure recovery | timeout/429/connection reset and bounded retry/reconciliation | blind retry or ambiguous authorization state |

### Exit criteria

GV-04 can move to external review only when all seven tests have unique evidence IDs, redacted hashes, timezone-aware timestamps, source revision, role provenance, independent read-back and an external owner decision. Passing local OIDC shape validation in `deployment_readiness.py` is not sufficient.

## 3. GV-08 — Device Trust and key custody validation package

### Preconditions

The OEM/custody owner must identify the manufacturer CA or approved HSM/secure-element boundary, key ceremony participants, dual-control approvers, device inventory, rotation policy, revocation distribution and lost-device process. Production private keys, factory master secrets and device seed maps are prohibited in source, database, logs and evidence.

### Test matrix

| ID | Test | Required evidence | Stop condition |
|---|---|---|---|
| KT-001 | Provenance/identity | redacted device inventory, manufacturer reference and key ID | unverified device or duplicate identity |
| KT-002 | Key issuance | dual-control ceremony record and public-key fingerprint | private key export or single-person approval |
| KT-003 | Activation | active status, approver IDs and policy decision | activation without dual control |
| KT-004 | Signature verification | synthetic/non-production signed packet and verification transcript | invalid signature accepted |
| KT-005 | Rotation | new key, `previous_key_id`, old-key suspension and rollback | old key remains accepted after revocation policy |
| KT-006 | Revocation/lost device | incident ID, revoked terminal state and propagation/read-back | revoked/lost key reactivated |
| KT-007 | Offline/degraded behavior | safe degraded-trust and manual fallback evidence | trust failure silently stops monitoring or authorizes unsafe data |

### Exit criteria

GV-08 can move to external review only when custody owner and independent verifier confirm the key material boundary, rotation/revocation behavior and lost-device drill. Software fixture mode remains `UNVERIFIED` and cannot satisfy manufacturer hardware trust.

## 4. GV-06 — Acer Spin N17H2 bench package

### Preconditions

Use a dedicated non-production Acer Spin N17H2 fixture, disposable runtime paths and synthetic telemetry only. The operator must confirm `I_HAVE_A_NONPRODUCTION_LOOPBACK`. No live patient, production HIS, ward network or real device pairing is permitted.

### Test matrix

Use the existing S-001–S-015 procedure in `SERIAL_BENCH_VALIDATION_PLAN.md`:

| Group | Required cases | Evidence |
|---|---|---|
| Host/port | S-001, S-002 | Acer model/OS/driver/port, exclusivity, time source |
| Framing | S-003–S-009 | full/partial/back-to-back/truncated/CRC/oversize/noise results |
| Recovery | S-010, S-013, S-014 | disconnect/reconnect, bounded pressure, restart/replay protection |
| Trust/privacy | S-011, S-012, S-015 | Device Trust mode, no PII/secret/command forwarding, redacted audit |

The physical path must use an approved adapter/loopback fixture and exact serial parameters. The framing harness passing in software is only a software baseline; it does not validate the Acer port or sensor hardware.

### Exit criteria

GV-06 can move to external review only with S-001–S-015 evidence, fixture/driver identity, operator role, source revision, no-production-network attestation, redacted logs, power/thermal/soak results and independent witness verification. If no COM port enumerates, keep GV-06 `BLOCKED`; do not substitute a simulated port for physical evidence.

## 5. Common evidence record

Every test record must include:

```text
evidence_id
gate_id
test_case_id
source_revision
freeze_manifest_sha256
prepared_by_role
independent_verification_required=true
started_at_utc
observed_at_utc
completed_at_utc
expected_result
actual_result
status=PASS|FAIL|BLOCKED|REQUIRES_CLARIFICATION
failure_class
artifact_sha256
manifest_sha256
redaction=PASS
chain_of_custody_ref
independent_readback_ref
external_authority=NONE until signed external decision
clinical_validation_authorized=false
production_authorized=false
runtime_authority=NONE
```

No evidence record may contain private keys, bearer tokens, raw HN/AN/MRN/National ID, names, unrestricted clinical text, raw serial frames or production endpoint secrets. A failed test is evidence of a blocker, not a reason to bypass the gate.

## 6. Execution order and approvals

First obtain Wave 0 role appointments, signed scope, test window, stop authority and rollback approval. Then execute GV-04, GV-08 and GV-06 independently in isolated environments. Reopen a blocked gate before submitting new evidence. After each track, perform hash/read-back and independent verification; do not combine local simulation output with external evidence under one evidence class.

The package remains `EXECUTION_NOT_STARTED` until the external owner explicitly authorizes the test window. Local preparation, schema validation or software regression cannot set `EVIDENCE_SUBMITTED`, `PASSED`, `AUTHORIZED_BY_EXTERNAL_OWNER` or `production_authorized=true`.
