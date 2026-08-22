# P0 Identity/Transport Readiness Guard — Readiness Report

**โครงการ:** Smart Ward Hub Reconcile  
**วันที่ตรวจ:** 23 สิงหาคม 2026  
**Decision:** `P0_IDENTITY_TRANSPORT_SOFTWARE_VERIFIED_PENDING_LIVE_EVIDENCE`  
**ขอบเขต:** local-only, deterministic configuration fixtures; no network contact  
**สถานะผลิตภัณฑ์:** `CONTROLLED_PRODUCTION_PROTOTYPE` / `NOT_PRODUCTION_READY`

## 1. สรุปผล / Executive Summary

P0 Identity/Transport Readiness Guard ตรวจรูปร่าง configuration ของ OIDC และ mTLS ด้วย deterministic fixtures โดยไม่ติดต่อ issuer, JWKS endpoint, TLS peer หรือ hospital network. ผลตรวจยืนยันว่า OIDC ต้องใช้ HTTPS issuer/JWKS, audience ต้องมีค่า, algorithm ต้องอยู่ใน safe allowlist และห้าม `NONE`; mTLS ต้องมี certificate/key/CA metadata, client certificate requirement และ private-key mode ที่ไม่เปิดให้ group/other access.

ผลนี้ยืนยัน **local configuration/file-hygiene semantics** เท่านั้น. ไม่ใช่หลักฐานว่า issuer หรือ JWKS ใช้งานได้, token signature/claims/scope mapping ถูกยอมรับจริง, certificate chain เชื่อถือได้, mutual TLS handshake สำเร็จ, rotation/revocation ทำงาน หรือ network segmentation ผ่านการทดสอบ. P0-002/P0-003 จึงยังต้องใช้หลักฐานจริงจาก IdP, CA และเครือข่ายของโรงพยาบาล.

## 2. ผลตรวจหลัก / Control Results

| Control | ผลตรวจ / Result | หลักฐาน |
|---|---|---|
| OIDC auth mode | ผ่าน; ต้องเป็น `oidc` | `validate_oidc_fixture()` |
| OIDC issuer/JWKS | ผ่านเฉพาะ absolute HTTPS shape | deterministic fixture |
| OIDC algorithm | ผ่าน; `RS256` อยู่ใน allowlist; `NONE`/`HS256` ถูก reject | focused/adversarial suite |
| mTLS files | ผ่าน metadata ว่า cert/key/CA present | deterministic fixture |
| mTLS client certificate | ต้องเป็น required | focused test |
| Private-key permission | `0600` ผ่าน; `0640` ถูก reject | focused test |
| Secret markers | Bearer/private-key/API-key markers ถูก reject | focused test + source scan |
| Network contact | ไม่มีการติดต่อจริง | `live_network_contact_absent=true` |
| Live OIDC evidence | ยัง `UNVERIFIED` | evidence snapshot |
| Live mTLS evidence | ยัง `UNVERIFIED` | evidence snapshot |
| Authority boundary | `external_authority=NONE`, no promotion | evidence snapshot |
| External Gates | `7 BLOCKED / 3 OPEN / 0 PASSED` | evidence snapshot |

## 3. Machine-readable evidence

หลักฐานหลักอยู่ที่ `evals/micro_rag/evidence/p0-identity-transport-readiness-local.json`. Snapshot ระบุ `all_passed=true`, `evidence_scope=LOCAL_DETERMINISTIC_FIXTURE_ONLY`, `redaction_verified=true`, `patient_data_used=false` และ `raw_frames_recorded=false`.

| Field | ค่า |
|---|---|
| `generated_at_utc` | `2026-08-22T19:34:46.410781Z` |
| `oidc_local_configuration_valid` | `true` |
| `mtls_local_configuration_valid` | `true` |
| `live_issuer_reachable` | `false` — ไม่ได้แปลว่า live endpoint ล้มเหลว; หมายถึงไม่ได้ติดต่อ |
| `live_jwks_rotation_verified` | `false` |
| `live_token_acceptance_verified` | `false` |
| `live_handshake_verified` | `false` |
| `live_rotation_verified` | `false` |
| `live_revocation_verified` | `false` |
| `external_submission_allowed` | `false` |
| `external_transmission_performed` | `false` |
| `authorization_promoted` | `false` |

## 4. Focused และ phase-end verification

Focused/adversarial suite ผ่าน **5 cases** ได้แก่ valid local-only readiness, OIDC mode/HTTPS/algorithm rejection, mTLS client-certificate/permission/CA rejection, unknown-field/secret-marker rejection และ returned-evidence mutation isolation.

Phase-end hardening ผ่านรายการต่อไปนี้:

| Gate | Result |
|---|---|
| Focused suite rerun | `PASSED` |
| AST network/provider/transport/scheduler import ban | `PASSED` |
| Live-evidence and secret-marker scan | `PASSED` |
| Runtime and authority boundary | `PASSED` |
| Exporter round-trip on temporary path | `PASSED` |
| Returned-evidence mutation isolation | `PASSED` |
| `git diff --check` | `PASSED` |

Exporter round-trip ใช้ temporary path เพื่อไม่เขียนทับ tracked evidence ระหว่าง master regression และไม่สร้าง freeze drift.

## 5. Live evidence ที่ยังต้องมี / Residual External Evidence

ก่อนพิจารณา real identity/transport integration ต้องมีหลักฐานจากเจ้าของระบบจริง ได้แก่ issuer discovery/JWKS reachability, signed token acceptance, `iss`/`aud`/`exp`/`iat`/scope mapping, key rotation และ revocation, certificate chain/CA trust, mutual TLS handshake, client-certificate authorization, renewal/revocation, route isolation และ network segmentation.

การเติมค่า fixture, static token หรือ HTTPS URL ใน repository ไม่สามารถแทนหลักฐานดังกล่าวได้. ห้ามนำ `P0_IDENTITY_TRANSPORT_SOFTWARE_VERIFIED_PENDING_LIVE_EVIDENCE` ไปตีความเป็น production identity readiness.

## 6. การทำซ้ำ / Reproduction

```text
cd /home/ubuntu/smart-ward-hub-reconcile
PYTHONDONTWRITEBYTECODE=1 /home/ubuntu/.venvs/smart-ward-audit/bin/python3 p0_identity_transport_readiness_guard.py
PYTHONDONTWRITEBYTECODE=1 /home/ubuntu/.venvs/smart-ward-audit/bin/python3 test_p0_identity_transport_readiness_guard.py
PYTHONDONTWRITEBYTECODE=1 /home/ubuntu/.venvs/smart-ward-audit/bin/python3 test_p0_identity_transport_readiness_guard_phase_end_hardening.py
PYTHONDONTWRITEBYTECODE=1 /home/ubuntu/.venvs/smart-ward-audit/bin/python3 export_p0_identity_transport_readiness_guard.py
```

คำสั่งทั้งหมดเป็น local-only และไม่มี network/provider/transport operation. Exporter เขียน evidence path เฉพาะเมื่อเรียกโดยตรง; phase-end gate ใช้ temporary path.

## 7. Claim boundary

> `P0_IDENTITY_TRANSPORT_SOFTWARE_VERIFIED_PENDING_LIVE_EVIDENCE` หมายถึง local OIDC/mTLS configuration contract ผ่าน deterministic checks เท่านั้น ไม่ใช่ live identity, handshake, rotation, revocation หรือ segmentation evidence.

ค่าล็อกคือ `external_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false`, `runtime_authority=NONE` และ `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`. External Gates ยังคง **7 `BLOCKED` / 3 `OPEN` / 0 `PASSED`**.

## 8. Repository evidence

- `p0_identity_transport_readiness_guard.py`
- `export_p0_identity_transport_readiness_guard.py`
- `test_p0_identity_transport_readiness_guard.py`
- `test_p0_identity_transport_readiness_guard_phase_end_hardening.py`
- `evals/micro_rag/evidence/p0-identity-transport-readiness-local.json`
- `validate_oidc_config.py`
- `validate_mtls_config.py`
- `test_p0_oidc_config.py`
- `test_p0_mtls_config.py`
- `P0_STATUS_REPORT.md`

## References

[1]: `P0_STATUS_REPORT.md` — current P0 OIDC/mTLS status and unverified live evidence boundary.
[2]: `validate_oidc_config.py` — canonical local OIDC configuration checks.
[3]: `validate_mtls_config.py` — canonical local mTLS file-hygiene checks.
[4]: `evals/micro_rag/evidence/p0-identity-transport-readiness-local.json` — machine-readable evidence snapshot.
