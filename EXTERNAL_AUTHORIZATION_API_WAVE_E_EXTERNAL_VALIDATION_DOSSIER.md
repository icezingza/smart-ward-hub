# External Authorization API — Wave E Non-Production Validation Dossier

**ตรวจเมื่อ:** 2026-08-20
**สถานะ:** `EXTERNAL_VALIDATION_NOT_STARTED`
**Evidence class:** `EXTERNAL_UNVERIFIED`
**ขอบเขต:** เตรียมการทดสอบกับ external endpoint ใน non-production เท่านั้น; ไม่มี credential, patient data, production traffic หรือ authorization decision ในเอกสารนี้

## Executive boundary

เอกสารนี้เป็น package สำหรับแต่งตั้ง owner, อนุมัติ test window และเตรียม independent verification ของ External Authorization API เท่านั้น ผลจาก local simulator และ Wave A–D regression เป็น software evidence ไม่ใช่หลักฐานของ endpoint, OIDC/mTLS, ACL, signed response, trusted clock, external custody หรือ reviewer จริง

> Local code ห้ามสร้าง `AUTHORIZED_BY_EXTERNAL_OWNER` และห้ามเปลี่ยน `external_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false`, `runtime_authority=NONE` หรือ `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION` ก่อนมี external decision ที่ตรวจสอบได้จาก owner ภายนอก

## Current readiness

| Boundary | Current status | Evidence class | Required before execution |
|---|---|---|---|
| Local simulator Wave A–D | `SOFTWARE_VERIFIED` / `SIMULATION_ONLY` ตาม control | Repository evidence | master regression และ evidence hash |
| External endpoint | `NOT_PROVISIONED` | `EXTERNAL_UNVERIFIED` | named service owner, non-production URL, health contract |
| OIDC/JWKS | `NOT_PROVISIONED` | `EXTERNAL_UNVERIFIED` | approved test tenant, issuer/audience/JWKS and rotation plan |
| mTLS | `NOT_PROVISIONED` | `EXTERNAL_UNVERIFIED` | test CA, client certificate, renewal/revocation procedure |
| ACL and network | `NOT_PROVISIONED` | `EXTERNAL_UNVERIFIED` | allowlist, segmentation, firewall and denied-path transcript |
| Signed response | `NOT_PROVISIONED` | `EXTERNAL_UNVERIFIED` | key ID, trust chain, signature verification and independent read-back |
| Custody/WORM | `NOT_PROVISIONED` | `EXTERNAL_UNVERIFIED` | independent append-only store, trusted timestamp and retention owner |
| External reviewer/stop authority | `NOT_APPOINTED` | `EXTERNAL_UNVERIFIED` | signed scope, test window, stop authority and recovery approval |
| Clinical authorization | `NOT_AUTHORIZED` | `CLINICAL_GOVERNANCE_UNVERIFIED` | clinical owner/committee decision and separate validation protocol |
| Production claim | `PROHIBITED` | `BLOCKER_RECORD` | all applicable external, hardware and clinical gates passed |

## Required external roles

| Role | Minimum responsibility | Appointment evidence | Current status |
|---|---|---|---|
| External Authorization service owner | endpoint, API contract, availability and incident contact | signed appointment and service reference | `PENDING` |
| Identity owner | OIDC issuer, JWKS, claims, rotation and revocation | test-tenant record and owner approval | `PENDING` |
| Transport/security owner | mTLS CA, certificate lifecycle, ACL and segmentation | signed test-window scope | `PENDING` |
| Evidence custodian | hashes, redaction, chain-of-custody and artifact transfer | custodian appointment | `PENDING` |
| Independent verifier | verifies receipt, response authenticity, read-back and findings | independent appointment | `PENDING` |
| Stop authority | can halt test on safety, privacy, identity, integrity or infrastructure trigger | stop-authority record | `PENDING` |
| Clinical governance owner | confirms clinical boundary and excluded use | committee/owner decision | `PENDING` |

## Entry criteria

External execution must not begin until every criterion below is recorded as `TRUE` by the responsible owner. A local test cannot self-satisfy an external criterion.

| ID | Entry criterion | Required artifact | Fail-closed action if absent |
|---|---|---|---|
| E-01 | named external owners and independent verifier appointed | signed role appointment record | remain `EXTERNAL_VALIDATION_NOT_STARTED` |
| E-02 | test scope, out-of-scope data, expiry and rollback signed | signed scope with timezone-aware expiry | do not open endpoint access |
| E-03 | isolated non-production endpoint and test tenant available | endpoint identity and environment record | do not send request |
| E-04 | synthetic-only payload and zero-PII scan approved | redacted fixture manifest and scan result | reject payload and stop |
| E-05 | OIDC/JWKS and mTLS materials provisioned through approved custody | redacted metadata/certificate transcript | fail closed on missing or invalid identity |
| E-06 | ACL, DNS, firewall and network segmentation approved | allow/deny transcript and owner sign-off | block connection |
| E-07 | clock, expiry and revocation test plan approved | trusted-time/reference-clock record | do not interpret decision |
| E-08 | independent evidence capture and read-back path available | custody/WORM and verifier procedure | retain local simulation only |
| E-09 | stop authority and incident channel reachable | stop record and escalation contact | do not start test window |
| E-10 | clinical and production authorization flags remain false | preflight response snapshot | stop and preserve evidence if changed |

## Test matrix

| ID | Test | Procedure | Expected fail-closed result | Evidence artifact | Owner |
|---|---|---|---|---|---|
| T-01 | Endpoint identity | connect only to approved non-production endpoint and record certificate/service identity | unknown endpoint rejected; no submission | redacted TLS/service identity transcript | Transport owner |
| T-02 | OIDC issuer/audience/JWKS | use synthetic test identity; exercise valid, wrong issuer, wrong audience, unsafe algorithm and expired token | invalid token rejected without status mutation | redacted token-validation transcript | Identity owner |
| T-03 | mTLS lifecycle | valid handshake, wrong CA, expired client cert, revoked cert and renewal | invalid chain/expiry/revocation rejected | handshake/renewal/revocation transcript | Transport owner |
| T-04 | ACL and segmentation | allowed source, denied source, wrong route and blocked port | denied path returns typed transport error; no retry storm | firewall/ACL transcript | Security owner |
| T-05 | Version negotiation | supported contract, unsupported version, backward-incompatible field and missing version | unsupported contract rejected; no interpretation of status | request/response hashes and error transcript | API owner |
| T-06 | Governance binding | submit current frozen package, wrong manifest, wrong scope/window, expired window and changed freeze | package mismatch or expired scope rejected; gate remains blocked | package-binding transcript | Evidence custodian |
| T-07 | Idempotency and uncertain commit | induce timeout after remote commit, retry same key, retry changed payload and reconcile | no duplicate; `COMMIT_UNKNOWN` enters reconciliation; changed payload rejected | correlation/reconcile transcript | API owner |
| T-08 | Decision expiry/revocation | poll before expiry, at expiry, after expiry, revoke, stale cache and restart | expired/revoked/stale status cannot promote; resubmission required | signed decision/read-back and cache invalidation transcript | Independent verifier |
| T-09 | Response authenticity | verify signed response, wrong signature, wrong key ID, wrong scope, missing independent read-back | untrusted response is `BLOCKED`; no authorization flags change | signature verification and read-back transcript | Independent verifier |
| T-10 | Audit/custody | append, read-back, tamper attempt, retention lookup and recovery | integrity/custody failure creates incident and stops mutation | external receipt, trusted timestamp and custody transcript | Evidence custodian |
| T-11 | Retry and rate limiting | transient timeout, connection reset, 429, bounded retry and auth failure | bounded retry; no blind retry for uncertain commit; stop on non-retryable failure | retry/429 transcript | API owner |
| T-12 | Stop/recovery | invoke safety/privacy/identity/integrity stop trigger and attempt restart | state-changing commands remain blocked until explicit recovery approval | stop/restart/approval record | Stop authority |

## Evidence record schema

Every external test artifact must include the following fields before independent verification:

```text
record_id
prepared_at_utc
prepared_by_role
external_owner_role
independent_verification_required=true
environment=NON_PRODUCTION
request_correlation_id
contract_version
endpoint_identity_ref
identity_transport_ref
request_sha256
response_sha256
receipt_ref
trusted_timestamp_ref
scope_id
window_id
expiry
revocation_status
stop_authority_ref
chain_of_custody_ref
redaction=PASS
raw_identity_present=false
external_authority=NONE until independently verified
clinical_validation_authorized=false
production_authorized=false
runtime_authority=NONE
pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
claim_boundary=EXTERNAL_UNVERIFIED_PENDING_REVIEW
```

## Decision rules

A test may be recorded as `ACCEPTED_FOR_INDEPENDENT_REVIEW` only when the artifact is complete, redacted, hash-bound, time-bound, independently readable and linked to the signed scope. That state is not `PASSED`, is not clinical authorization, and is not production authorization. Any mismatch, missing receipt, invalid signature, expired scope, stale response, unknown clock state or custody gap returns the test to `BLOCKED` or `REQUIRES_CLARIFICATION`.

The 10 External Gates remain governed by `external_validation_package.py`. A local `reopen()` is required before resubmitting evidence to a previously blocked gate. Local acceptance of an evidence file cannot convert a gate to `PASSED` without the external owner and independent reviewer decision.

## Current blocker set

The dossier is not executable because there is no external endpoint, test IdP, mTLS material, ACL approval, custody service, named external reviewer, stop-authority appointment or clinical governance authorization in the repository. The Acer Spin N17H2 also has no enumerated COM port in the prior read-only inventory, so GV-06 remains blocked and the physical phrase `I_HAVE_A_NONPRODUCTION_LOOPBACK` is not asserted here.

## Handoff package

- `EXTERNAL_AUTHORIZATION_API_SIMULATION_CONTRACT.md`
- `EXTERNAL_AUTHORIZATION_API_DECISION_LIFECYCLE.md`
- `EXTERNAL_AUTHORIZATION_API_FAIL_CLOSED_GAP_REGISTER.md`
- `EXTERNAL_AUTHORIZATION_API_WAVE_A_D_HARDENING_PLAN.md`
- `WAVE_0_GOVERNANCE_HANDOFF_REPORT.md`
- `WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md`
- `GV10_INDEPENDENT_REVIEW_DOSSIER.md`
- `EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md`
- `PRODUCTION_READINESS_EVIDENCE_AUDIT.md`

**Product statement:** controlled production prototype; P0-hardened software baseline; functional verification passed; pilot-ready foundation; clinical validation pending; pilot deployment configuration pending.

**Do not claim:** clinical-ready, production-ready, tamper-proof or HIPAA/PDPA compliant 100% from local functional tests or simulation.

## References

[1]: EXTERNAL_AUTHORIZATION_API_SIMULATION_CONTRACT.md
[2]: EXTERNAL_AUTHORIZATION_API_DECISION_LIFECYCLE.md
[3]: EXTERNAL_AUTHORIZATION_API_FAIL_CLOSED_GAP_REGISTER.md
[4]: EXTERNAL_AUTHORIZATION_API_WAVE_A_D_HARDENING_PLAN.md
[5]: WAVE_0_GOVERNANCE_HANDOFF_REPORT.md
[6]: WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md
[7]: GV10_INDEPENDENT_REVIEW_DOSSIER.md
[8]: EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md
[9]: PRODUCTION_READINESS_EVIDENCE_AUDIT.md

**Prepared by role:** `integration_owner`
**Independent verification required:** `true`
**Chain-of-custody reference:** `repo://EXTERNAL_AUTHORIZATION_API_WAVE_E_EXTERNAL_VALIDATION_DOSSIER.md`
**Redaction:** `PASS`
**External authority:** `NONE`
**Clinical validation authorized:** `false`
**Production authorized:** `false`
**Runtime authority:** `NONE`
