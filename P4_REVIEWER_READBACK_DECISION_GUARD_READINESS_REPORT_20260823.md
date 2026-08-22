# P4 Reviewer Read-back Decision Guard — Readiness Report

**โครงการ:** Smart Ward Hub Reconcile  
**วันที่ตรวจ:** 23 สิงหาคม 2026 (ผล fixture timestamp ภายใน evaluator: `2026-08-22T18:15:00Z`)  
**Decision:** `P4_REVIEWER_READBACK_GUARD_VERIFIED`  
**ขอบเขต:** local-only, read-only, deterministic software evidence; no external transmission  
**Claim boundary:** `CONTROLLED_PRODUCTION_PROTOTYPE` / `NOT_PRODUCTION_READY`

## 1. สรุปผล / Executive Summary

P4 Reviewer Read-back Decision Guard ตรวจวงจรการอ่านกลับสถานะ external decision แบบ local-only โดยใช้ deterministic fixtures เท่านั้น. Guard ยืนยันว่า fresh poll เป็น `POLL_ACCEPTED_UNVERIFIED`, stale/future response ถูกปฏิเสธเป็น `STALE_RESPONSE_REJECTED`, external `BLOCKED` update ถูกจำลองเป็น `BLOCKED_SIMULATION` โดยยังคง `trusted=false`, `external_decision_verified=false` และ `authorization_promoted=false`, และ local actor ไม่สามารถใช้ช่อง external-update เพื่อเปลี่ยน lifecycle ได้.

ผลนี้พิสูจน์ **software contract และ fail-closed behavior** ของ read-back boundary เท่านั้น. ไม่ใช่การแต่งตั้ง independent reviewer, ไม่ใช่การตรวจ signature/custody ของผู้มีอำนาจจริง, ไม่ใช่ external submission, ไม่ใช่ clinical validation และไม่ใช่ production authorization.

## 2. ผลตรวจหลัก / Control Results

| Control | ผลตรวจ / Result | หลักฐาน |
|---|---|---|
| Local decision snapshot schema | ผ่าน; `TEMPLATE_SNAPSHOT` valid | `p4_reviewer_readback_decision_guard.py`, `evals/micro_rag/evidence/external-decision-record-local-20260821.json` |
| Received decision fixture | ผ่าน; decision `BLOCKED`, non-authorizing | deterministic fixture ใน `p4_reviewer_readback_decision_guard.py` |
| Fresh poll | `POLL_ACCEPTED_UNVERIFIED`; `trusted=false` | evidence snapshot `fresh_poll_result` |
| Stale/future poll | `STALE_RESPONSE_REJECTED` | evidence snapshot `stale_poll_result` |
| External update | `BLOCKED_SIMULATION`; ไม่ promote authority | evidence snapshot `external_update_result` |
| Local actor update | rejected; actor ต้องเป็น external authority | `unauthorized_local_update_rejected=true` |
| Audit/revision integrity | ผ่าน; `audit_event_count=2`, chain valid | evaluator `audit_chain_valid=true` |
| Appointment dependency | ยังเป็น template-only; `appointment_confirmed=false` | P4 appointment-plan readiness evidence |
| Reviewer handoff dependency | appointment-only; `ready_for_external_review=false` | P4 handoff readiness evidence |
| Export boundary | round-trip ผ่าน; fixture-only/read-only/non-authorizing | `export_p4_reviewer_readback_decision_guard.py` |

## 3. ค่าขอบเขตที่ถูกล็อก / Locked Boundary

Evidence snapshot ยืนยันค่าต่อไปนี้โดยไม่เปิดช่องให้ local evaluator self-authorize:

| Field | Locked value |
|---|---|
| `external_authority` | `NONE` |
| `external_decision` | `NOT_ISSUED` |
| `external_decision_verified` | `false` |
| `external_readback_trusted` | `false` |
| `clinical_validation_authorized` | `false` |
| `production_authorized` | `false` |
| `runtime_authority` | `NONE` |
| `pilot_gate_status` | `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION` |
| `appointment_confirmed` | `false` |
| `reviewer_appointment` | `PENDING_EXTERNAL_APPOINTMENT` |
| `ready_for_external_appointment` | `true` — local preparation only |
| `ready_for_external_review` | `false` |
| `submission_allowed` | `false` |
| `external_submission_allowed` | `false` |
| `external_transmission_performed` | `false` |
| `runtime_mutation_performed` | `false` |
| `authorization_promoted` | `false` |
| `production_ready` | `false` |
| `hardware_evidence` | `UNVERIFIED` |

> `P4_REVIEWER_READBACK_GUARD_VERIFIED` หมายถึง local read-back control ทำงานครบตาม contract เท่านั้น ไม่ได้หมายความว่า external decision ถูกยืนยันแล้ว หรือระบบได้รับ authority ใด ๆ.

## 4. Fail-closed และ adversarial coverage

Focused/adversarial suite ผ่าน **10 cases** ได้แก่ valid unverified read-back, local snapshot authorization mutation, appointment dependency mutation, reviewer-handoff promotion mutation, malformed/unknown/authorization-promoted decision records, secret/raw-identity redaction markers, stale/future/hash-mismatch polls, local/external no-self-authorization, snapshot boundary isolation และ audit-chain tamper detection. การ mutate ค่า authorization ใน local snapshot หรือ received decision record ทำให้ guard คืน `P4_REVIEWER_READBACK_GUARD_BLOCKED` หรือ validator ปฏิเสธ input พร้อม remediation/error แทนการยอมรับค่าที่ผิด.

Phase-end hardening gate ผ่านรายการต่อไปนี้:

| Gate | ผล |
|---|---|
| Focused suite rerun | `PASSED` |
| AST import ban: network/provider/transport/scheduler | `PASSED` |
| Poll/update/revision and locked-boundary assertions | `PASSED` |
| Exporter round-trip and locked export boundary | `PASSED` |
| Redaction and private-key marker scan | `PASSED` |
| No-self-authorization assertions | `PASSED` |
| `git diff --check` | `PASSED` |

## 5. หลักฐานและการทำซ้ำ / Evidence and Reproduction

ไฟล์ควบคุมหลักคือ `p4_reviewer_readback_decision_guard.py`, focused suite คือ `test_p4_reviewer_readback_decision_guard.py`, phase-end gate คือ `test_p4_reviewer_readback_decision_guard_phase_end_hardening.py` และ exporter คือ `export_p4_reviewer_readback_decision_guard.py`. Local machine-readable evidence อยู่ที่ `evals/micro_rag/evidence/p4-reviewer-readback-decision-guard-local.json`.

คำสั่งทำซ้ำแบบ local-only:

```text
cd /home/ubuntu/smart-ward-hub-reconcile
/home/ubuntu/.venvs/smart-ward-audit/bin/python3 ./test_p4_reviewer_readback_decision_guard.py
/home/ubuntu/.venvs/smart-ward-audit/bin/python3 ./test_p4_reviewer_readback_decision_guard_phase_end_hardening.py
/home/ubuntu/.venvs/smart-ward-audit/bin/python3 ./export_p4_reviewer_readback_decision_guard.py
```

คำสั่งข้างต้นไม่เปิด network transport, ไม่เรียก provider, ไม่ใช้ real reviewer/API/IdP/HIS/hardware และไม่เขียน runtime state ของระบบ. Exporter เขียนเฉพาะ local evidence path ที่กำหนด.

## 6. สิ่งที่ยังไม่ยืนยัน / Residual External Dependencies

การแต่งตั้ง reviewer จริงยังต้องมี appointing authority, signed scope, conflict declaration, role separation, reviewer acceptance และ independent read-back/custody record. External decision จริงยังต้องมี authenticated endpoint, signature/trust-chain verification, trusted time, expiry/revocation, custody receipt และ independent reviewer read-back. Read-back guard นี้ไม่สามารถสร้างหรือยืนยันข้อมูลดังกล่าวแทนองค์กรภายนอกได้.

External Gates ยังคง **7 `BLOCKED` / 3 `OPEN` / 0 `PASSED`**. Fixed Hub Acer Spin N17H2, BMAX i11_s roaming candidate, actual COM/driver behavior, HIS/FHIR, IdP/mTLS, manufacturer key custody, external WORM/timestamp, clinical governance, staff workflow และ independent review ยังคง `Unverified`/pending ตาม scope เดิม. Local software evidence นี้ไม่ปลด blocked gate และไม่เปลี่ยนสถานะ product.

## 7. Repository evidence list

- `p4_reviewer_readback_decision_guard.py`
- `export_p4_reviewer_readback_decision_guard.py`
- `test_p4_reviewer_readback_decision_guard.py`
- `test_p4_reviewer_readback_decision_guard_phase_end_hardening.py`
- `evals/micro_rag/evidence/p4-reviewer-readback-decision-guard-local.json`
- `external_decision_lifecycle.py`
- `external_decision_record.py`
- `P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_20260822.md`
- `P4_INDEPENDENT_REVIEWER_HANDOFF_READINESS_REPORT_20260822.md`
- `evals/micro_rag/evidence/external-decision-record-local-20260821.json`

**Product state:** `CONTROLLED_PRODUCTION_PROTOTYPE`; **not production-ready**; external authority `NONE`; clinical validation pending; pilot gate `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.
