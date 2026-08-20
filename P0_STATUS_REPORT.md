# Smart Ward Hub — P0 Backlog Status Report

**วันที่:** 20 สิงหาคม 2026 (GMT+7)  
**สถานะรวม:** P0-hardened software baseline; controlled production prototype; pilot-ready foundation; pilot deployment configuration pending; clinical validation pending

## Executive summary

การตรวจสอบ P0 backlog เทียบกับ code, tests, contracts และ operations runbook พบว่าไม่มี P0 รายการใดที่ควรปิดเป็น `Verified` ในขณะนี้ แต่มี 4 รายการที่สามารถยกระดับจาก `Planned` เป็น `In Progress` ได้ด้วยงาน software/contract validation ใน sandbox ส่วน P0-005 ยังต้องใช้ Acer Spin N17H2 จริงและจึงคงสถานะ `Planned`

งานที่ทำต่อแล้วในรอบนี้คือการเพิ่ม structured acknowledgment contract สำหรับ HIS/FHIR sync, เพิ่ม sandbox HIS/Admission Gateway contract test ที่ครอบคลุม opaque tokenization, TTL, revocation, idempotency และ acknowledgment gate, เพิ่ม OIDC configuration validator, เพิ่ม mTLS file-hygiene validator, เพิ่ม software recovery fault harness และออกแบบ Zero-Trust trust boundaries ใน `architecture.md` พร้อมเอกสารรายละเอียดแยก

## P0 status matrix

| ID | สถานะปัจจุบัน | สิ่งที่ยืนยันได้ | Blocker หรือ residual risk | หลักฐานที่ต้องใช้เพื่อปิด |
|---|---|---|---|---|
| P0-001 | **In Progress** | `test_p0_his_admission_contract.py` ผ่าน opaque tokenization, token TTL/revocation, outside admission idempotency, failure retention, mismatched acknowledgment rejection และ exact-scope purge | Sandbox test double ไม่ใช่ HIS จริง; HIS ยังไม่ยืนยัน FHIR version/profile, terminology, patient-reference policy, issuer, CA, error body, support และ idempotency behavior | Hospital HIS contract test พร้อม real profile/version, real mTLS/OIDC transport และ purge/retention transcript |
| P0-002 | **In Progress** | Local validator ตรวจ `SW_AUTH_MODE`, issuer, audience, HTTPS JWKS URL และ safe algorithms; missing config fail-closed | ยังไม่มี real IdP/test tenant; ไม่ได้พิสูจน์ JWKS discovery, key rotation, claim mapping, token expiry, revocation หรือ role/scopes จริง | Redacted transcript จาก real issuer/JWKS, rotation/revocation test, scope mapping และ failure cases |
| P0-003 | **In Progress** | Local validator ตรวจ cert/key/CA file presence และ reject private key ที่ group/other-readable โดยไม่อ่าน key material; launcher fail-closed | ยังไม่มี CA chain จริง, mutual handshake, client cert identity, renewal/revocation, clock behavior หรือ network segmentation | Real test CA/PKI handshake, renewal, expired/revoked cert rejection, route/firewall evidence |
| P0-004 | **In Progress** | `test_p0_recovery.py` และ `power_loss_recovery_harness.py` ผ่าน atomic restart, stale temp isolation, corrupt JSON fail-closed, unsupported/malformed payload handling, PII-bearing checkpoint rejection, sequence-inconsistency rejection และ SQLite WAL + synchronous FULL reopen check | เป็น software fault injection เท่านั้น; ยังไม่ทดสอบ power cut จริง, disk-full, filesystem corruption, storage controller, UPS/battery หรือ OS recovery บน Acer | Controlled hardware power cut, disk-full/corruption drill, reboot/service recovery transcript และ data-integrity comparison |
| P0-005 | **Planned** | Hardware choice documented: Acer Spin N17H2 as Fixed Hub candidate | Physical Acer, charger/battery, thermal, touchscreen, network, USB/NFC/BLE gateway and service supervisor are not available to this sandbox | Bench protocol executed on Acer with serialised evidence, soak test, reboot, network interruption and service recovery |

## Technical blockers and risks

### 1. HIS acknowledgment is contract-sensitive

The local endpoint can now require a structured acknowledgment, but it cannot invent the hospital’s accepted FHIR profiles, terminology, patient-reference semantics or receiving-system identity. Treating a local `200` as sufficient would create a purge risk; the new code prevents the simplest version of that failure but the remote contract remains an external dependency.

### 2. OIDC readiness is configuration-ready, not identity-verified

The code fails closed when OIDC configuration is incomplete and validates local URL/algorithm shape. It does not prove that a real issuer signs acceptable tokens, publishes the expected JWKS, rotates keys safely, maps claims to scopes, revokes sessions or rejects expired/replayed tokens. This is a real IdP integration gate, not a documentation gap.

### 3. mTLS file hygiene is not mTLS trust

The new validator protects a basic local failure mode—missing files and overly broad private-key permissions—without exposing key content. It does not validate certificate chain trust, server/client identity, renewal, revocation, time synchronization, mutual handshake or route isolation. A certificate file existing on disk must not be treated as proof of a trusted transport.

### 4. Software recovery is not power-loss evidence

The software harness confirms the intended checkpoint/WAL behavior and fail-closed PII/sequence invariants under controlled process/file fixtures. It cannot reproduce the failure modes that matter on a physical ward host: abrupt power removal during commit, battery depletion, disk-full, filesystem errors, SSD/controller behavior, OS boot recovery and service supervisor ordering.

### 5. Zero-Trust requires enforcement across deployment boundaries

The architecture now defines per-zone identity, scope, freshness, segmentation, egress and approval gates. Several controls remain unverified because the real IdP, PKI, MDM, host firewall, encrypted volume, hospital network and external anchor are not configured in the sandbox.

## Work completed in this review

| Change | Evidence |
|---|---|
| Structured HIS/FHIR acknowledgment fields | `schemas.py`, `main.py`, `test_fhir.py` |
| Sandbox HIS/Admission Gateway contract | `his_admission_gateway_contract.py`, `test_p0_his_admission_contract.py` |
| Bare acknowledgment rejection | `test_fhir.py` passes with HTTP 422 before purge |
| Bundle identity mismatch rejection | `test_fhir.py` passes with HTTP 409 before purge |
| OIDC local configuration validator | `validate_oidc_config.py`, `test_p0_oidc_config.py` pass |
| mTLS local file-hygiene validator | `validate_mtls_config.py`, `test_p0_mtls_config.py` pass |
| Recovery software harness | `test_p0_recovery.py`, `power_loss_recovery_harness.py` and `test_power_loss_recovery_harness.py` pass; checkpoint PII/sequence invariants are software-verified; physical failures remain unverified |
| Master regression integration | `run_all_tests.py` includes the HIS contract and recovery fault harness tests; complete suite passed |
| Zero-Trust architecture design | `architecture.md` section 7 and `ZERO_TRUST_TRUST_BOUNDARIES.md` |
| Hardware acceptance preparation | `P0_HARDWARE_BENCH_CHECKLIST.md` prepared; physical execution pending |
| Backlog status/evidence notes | `tasks.md` P0 section updated |

## Verification result

After the structured acknowledgment change and new P0 validators were registered, the complete master regression suite passed, including Phases 1–6, Device Trust, ward workflow, Outside-in Admission, roaming synchronization, reliability validation, 30-day software simulation, OIDC local configuration validation, mTLS file-hygiene validation and the P0 software recovery harness. This remains software evidence; the harness explicitly reports real power cut, disk-full, filesystem corruption, live IdP and live PKI behavior as `Unverified`.

## Recommended next action order

1. Obtain hospital decisions and a sandbox endpoint for P0-001, then run the contract test with real profile/version and structured acknowledgment body.
2. Obtain a non-production OIDC issuer and test tenant; run P0-002 with redacted token/rotation/revocation evidence.
3. Obtain a test CA and certificate set; run P0-003 on an isolated network and verify renewal/revocation failure behavior.
4. Execute the recovery harness plus controlled power-loss/storage drills on the Acer Spin N17H2 for P0-004 and P0-005.
5. Only after those gates, decide whether to return to BMAX client/UI or begin P1 backup/key-custody/clinical shadow-mode work.

## Claim boundary

The correct conclusion is **functional verification passed for the added software checks**, not real HIS/IdP/PKI/hardware validation. Smart Ward Hub remains a **controlled production prototype** and **pilot-ready foundation**, with **pilot deployment configuration pending** and **clinical validation pending**.
