# P0 HIS/FHIR Contract Readiness Guard — Readiness Report

**โครงการ:** Smart Ward Hub Reconcile  
**วันที่ตรวจ:** 23 สิงหาคม 2026  
**Decision:** `P0_HIS_FHIR_CONTRACT_SOFTWARE_VERIFIED_PENDING_EXTERNAL_DECISIONS`  
**ขอบเขต:** local-only, deterministic fixture, software contract verification  
**สถานะผลิตภัณฑ์:** `CONTROLLED_PRODUCTION_PROTOTYPE` / `NOT_PRODUCTION_READY`

## 1. สรุปผล / Executive Summary

P0 HIS/FHIR Contract Readiness Guard ตรวจ proposed Hub-facing handover envelope และ structured acknowledgment ด้วย deterministic fixtures เท่านั้น. ผลตรวจยืนยันว่า Hub-facing payload ใช้ opaque token เท่านั้น, raw HN/AN-style identity ไม่ถูกยอมรับ, idempotency key อยู่ใน envelope เดียวกัน, generic `200` ที่ไม่มี structured acknowledgment ไม่ทำให้ purge ได้, transport failure คงข้อมูล local ไว้ และ acknowledgment ที่ตรง bundle จะให้เพียง `PURGE_ELIGIBLE_SIMULATION` แบบ exact-scope โดยยังไม่ execute purge.

ผลนี้เป็น **software contract evidence** ไม่ใช่หลักฐานการเชื่อม HIS จริง, ไม่ใช่ FHIR conformance certification, ไม่ใช่ OIDC/mTLS identity evidence, ไม่ใช่ hospital authorization และไม่ใช่ clinical or production approval. Contract document เดิมยังจัด P0-001 เป็น `In Progress` จนกว่าจะได้รับการตัดสินใจจากโรงพยาบาลในเรื่อง version/profile, token issuer, patient-reference policy, acknowledgment/error contract, CA และ operational ownership.

## 2. ผลตรวจหลัก / Control Results

| Control | ผลตรวจ / Result | หลักฐาน |
|---|---|---|
| Hub-facing envelope | ผ่าน; exact fields และ opaque patient token | `p0_his_fhir_contract_readiness_guard.py` |
| Raw identity boundary | ผ่าน; raw HN/AN/MRN/NATIONAL_ID pattern ถูก reject | `test_p0_his_fhir_contract_readiness_guard.py` |
| Secret-marker redaction | ผ่าน; Bearer/private-key markers ถูก reject | focused test + phase-end scan |
| Idempotency | ผ่านใน deterministic envelope; key คงเดิมเมื่อ replay input เดิม | evidence `idempotency_key_stable=true` |
| Generic `200` | ผ่านแบบ fail-closed; `RETAINED_FOR_RETRY`, `purge_eligible=false` | evidence `generic_200_rejected=true` |
| Transport/error failure | ผ่าน; local data retained, no purge | `failure_ack_result` |
| Structured acknowledgment | ผ่าน; requires status 200, exact bundle, ack id, receiving system, time, version/profile | `validate_his_acknowledgment()` |
| Bundle mismatch | ผ่าน; mismatch rejected | evidence `mismatched_bundle_rejected=true` |
| Purge boundary | ผ่าน simulation only; exact window scope, `purge_executed=false` | `success_ack_result` |
| Authority boundary | ผ่าน; external authority remains `NONE` | evidence snapshot |
| External decision inputs | 9 items pending | `external_decisions_pending` |
| External transmission | ไม่เกิดขึ้น | `external_transmission_performed=false` |

## 3. Machine-readable evidence

หลักฐานหลักอยู่ที่ `evals/micro_rag/evidence/p0-his-fhir-contract-readiness-local.json`. Snapshot ระบุ `all_passed=true`, `evidence_scope=LOCAL_DETERMINISTIC_FIXTURE_ONLY`, `redaction_verified=true`, `patient_data_used=false` และ `raw_frames_recorded=false`.

| Field | ค่า |
|---|---|
| `generated_at_utc` | `2026-08-22T19:22:09.766510Z` |
| `external_decision_count` | `9` |
| `real_his_evidence` | `UNVERIFIED` |
| `real_mtls_oidc_evidence` | `UNVERIFIED` |
| `physical_hardware_evidence` | `UNVERIFIED` |
| `external_submission_allowed` | `false` |
| `external_transmission_performed` | `false` |
| `external_verification_performed` | `false` |
| `purge_executed` | `false` |
| `authorization_promoted` | `false` |

## 4. External decisions ที่ยังค้าง / Pending Hospital Decisions

Guard ระบุ pending inputs 9 กลุ่มต่อไปนี้โดยตั้งใจไม่สมมุติค่าแทนโรงพยาบาล:

1. FHIR version และ accepted profiles
2. Terminology และ Observation status policy
3. Patient-reference policy ระหว่าง Admission Gateway กับ HIS
4. Time zone, consent และ retention policy
5. Structured acknowledgment และ error contract
6. Idempotency behavior และ operational support path
7. Certificate authority และ transport identity
8. Token issuer, TTL และ revocation semantics
9. Monitoring endpoint และ operational owner

จนกว่าจะได้รับเอกสารหรือ transcript จริงจากเจ้าของระบบ ค่าเหล่านี้ต้องถือเป็น `Unverified`/pending. Local fixture ไม่สามารถเปลี่ยน P0-001 เป็น integration-ready หรือ production-ready ได้.

## 5. Focused และ phase-end verification

Focused/adversarial suite ผ่าน **6 cases** ได้แก่ valid software-only readiness, raw identity/secret rejection, generic-200 and failure retention, exact structured acknowledgment, invalid window/timestamp rejection และ returned-evidence mutation isolation.

Phase-end hardening ผ่านรายการต่อไปนี้:

| Gate | Result |
|---|---|
| Focused suite rerun | `PASSED` |
| AST network/provider/transport/scheduler import ban | `PASSED` |
| Positive authority and secret-marker scan | `PASSED` |
| Runtime locked-boundary assertions | `PASSED` |
| Exporter round-trip | `PASSED` |
| Evidence mutation isolation | `PASSED` |
| `git diff --check` | `PASSED` |

## 6. การทำซ้ำ / Reproduction

```text
cd /home/ubuntu/smart-ward-hub-reconcile
PYTHONDONTWRITEBYTECODE=1 /home/ubuntu/.venvs/smart-ward-audit/bin/python3 p0_his_fhir_contract_readiness_guard.py
PYTHONDONTWRITEBYTECODE=1 /home/ubuntu/.venvs/smart-ward-audit/bin/python3 test_p0_his_fhir_contract_readiness_guard.py
PYTHONDONTWRITEBYTECODE=1 /home/ubuntu/.venvs/smart-ward-audit/bin/python3 test_p0_his_fhir_contract_readiness_guard_phase_end_hardening.py
PYTHONDONTWRITEBYTECODE=1 /home/ubuntu/.venvs/smart-ward-audit/bin/python3 export_p0_his_fhir_contract_readiness_guard.py
```

คำสั่งทั้งหมดเป็น local-only และไม่มี network/provider/transport operation. Exporter เขียนเฉพาะ evidence path ภายใน repository.

## 7. Claim และ residual boundary

> `P0_HIS_FHIR_CONTRACT_SOFTWARE_VERIFIED_PENDING_EXTERNAL_DECISIONS` หมายถึง software contract ของ envelope/acknowledgment ทำงานตาม deterministic fixture และ fail-closed semantics เท่านั้น ไม่ได้หมายความว่า HIS/FHIR integration ถูกยืนยันแล้ว.

External Gates ยังคง **7 `BLOCKED` / 3 `OPEN` / 0 `PASSED`**. ค่าล็อกคือ `external_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false`, `runtime_authority=NONE` และ `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.

ยังไม่มีหลักฐานจริงของ hospital HIS/FHIR endpoint, issuer/JWKS, mTLS certificate chain/rotation/revocation, FHIR profile validation, clinical governance, Acer hardware/COM behavior, WORM custody หรือ independent reviewer decision. ห้ามนำ local contract fixture ไปใช้เป็น authorization หรือส่งข้อมูลผู้ป่วยจริง.

## 8. Repository evidence

- `p0_his_fhir_contract_readiness_guard.py`
- `export_p0_his_fhir_contract_readiness_guard.py`
- `test_p0_his_fhir_contract_readiness_guard.py`
- `test_p0_his_fhir_contract_readiness_guard_phase_end_hardening.py`
- `evals/micro_rag/evidence/p0-his-fhir-contract-readiness-local.json`
- `HIS_FHIR_INTEGRATION_CONTRACT.md`
- `his_admission_gateway_contract.py`
- `test_p0_his_admission_contract.py`

## References

[1]: `HIS_FHIR_INTEGRATION_CONTRACT.md` — existing HIS/FHIR integration contract and required hospital decisions.
[2]: `p0_his_fhir_contract_readiness_guard.py` — local evaluator and fail-closed contract rules.
[3]: `evals/micro_rag/evidence/p0-his-fhir-contract-readiness-local.json` — machine-readable evidence snapshot.
[4]: `test_p0_his_fhir_contract_readiness_guard_phase_end_hardening.py` — phase-end hardening gate.
