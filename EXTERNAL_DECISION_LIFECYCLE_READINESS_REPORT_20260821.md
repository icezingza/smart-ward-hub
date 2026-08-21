# External Decision Lifecycle Evaluator Readiness Report

**วันที่:** 21 สิงหาคม 2026 (GMT+7)  
**Task ID:** `EXTERNAL-DECISION-LIFECYCLE-001`  
**สถานะ:** `SOFTWARE_VERIFICATION_PASSED_EXTERNAL_AUTHORIZATION_PENDING`  
**Evidence class:** `LOCAL_SOFTWARE_SIMULATION`  
**Prepared by role:** `evidence_custodian`  
**External authority:** `NONE`  
**Independent reviewer:** `NOT_STARTED`

## 1. ขอบเขตและวัตถุประสงค์

รอบนี้เพิ่ม `external_decision_lifecycle.py` เพื่อเป็น evaluator แบบ deterministic สำหรับวงจรชีวิตของ external decision record ได้แก่ การเริ่มต้นจาก record ที่ได้รับ, การหมดอายุ, การเพิกถอนหรือ supersession, การ block simulation, การ reopen ด้วยเหตุผล, การ resubmission และการตรวจ stale polling โดย evaluator ทำงานใน local process เท่านั้นและไม่ติดต่อ provider, endpoint, scheduler หรือ external authority ใด ๆ

การทดสอบทั้งหมดในรายงานนี้เป็น **software simulation และ functional verification** จาก fixture ที่เก็บเฉพาะ opaque references ไม่ใช่ผลการทดสอบฮาร์ดแวร์ Acer Spin N17H2/BMAX i11_s, ไม่ใช่ clinical validation, ไม่ใช่ HIS/EMR production integration และไม่ใช่การตรวจลายเซ็นหรือ custody จริงจากหน่วยงานภายนอก

## 2. State machine ที่ implement

| State | Allowed next states | ความหมายเชิงควบคุม |
|---|---|---|
| `DECISION_PENDING_EXTERNAL_VERIFICATION` | `REQUIRES_CLARIFICATION`, `DECISION_EXPIRED`, `DECISION_REVOKED`, `BLOCKED_SIMULATION` | รับ record ไว้เพื่อการตรวจสอบ แต่ยังไม่ trusted และไม่ authorize |
| `REQUIRES_CLARIFICATION` | `DECISION_PENDING_EXTERNAL_VERIFICATION`, `DECISION_EXPIRED`, `DECISION_REVOKED`, `BLOCKED_SIMULATION` | ต้องขอข้อมูล/หลักฐานเพิ่มจาก boundary ภายนอก |
| `DECISION_EXPIRED` | `RESUBMISSION_REQUIRED`, `BLOCKED_SIMULATION` | หมดอายุและห้ามนำกลับมาใช้โดยแก้ record เดิม |
| `DECISION_REVOKED` | `RESUBMISSION_REQUIRED`, `BLOCKED_SIMULATION` | ถูกเพิกถอนหรือ superseded และห้ามใช้ต่อ |
| `BLOCKED_SIMULATION` | `REOPENED_WITH_REASON` | ถูกหยุดแบบ fail-closed จนกว่าจะมีเหตุผลและ role ที่กำหนด |
| `REOPENED_WITH_REASON` | `RECEIVED_FOR_SIMULATION`, `BLOCKED_SIMULATION` | เปิด simulation แบบมีเหตุผลตรวจสอบย้อนกลับได้ |
| `RESUBMISSION_REQUIRED` | `RECEIVED_FOR_SIMULATION` | ต้องสร้าง/รับ submission ใหม่ ไม่แก้ decision เดิม |
| `RECEIVED_FOR_SIMULATION` | `DECISION_PENDING_EXTERNAL_VERIFICATION`, `BLOCKED_SIMULATION` | ข้อมูลใหม่อยู่ใน simulation และยังไม่ verified |

ไม่มี transition ไปยัง `AUTHORIZED_BY_EXTERNAL_OWNER`, `READY_FOR_EXTERNAL_EXECUTION`, `PRODUCTION_AUTHORIZED` หรือ state ที่มีความหมายว่า clinical/production approval

## 3. Controls ที่ implement และตรวจแล้ว

| Control | หลักฐาน | ผล |
|---|---|---|
| Contract validation ก่อนสร้าง evaluator | `external_decision_lifecycle.py:117-124` เรียก `validate()` และบังคับ timezone-aware clock | PASS |
| Deterministic expiry | `external_decision_lifecycle.py:130-139, 184-192` | PASS |
| Revocation/supersession role boundary | `external_decision_lifecycle.py:194-200` อนุญาตเฉพาะ `external_authority` หรือ `independent_reviewer` | PASS |
| Resubmission ไม่แก้ record เดิม | `external_decision_lifecycle.py:209-213` และ transition `DECISION_EXPIRED/REVOKED → RESUBMISSION_REQUIRED` | PASS |
| Reopen ต้องใช้ stop/recovery role | `external_decision_lifecycle.py:215-220` | PASS |
| Stale/future polling rejection | `external_decision_lifecycle.py:234-269` ตรวจ age, revision และ event hash | PASS |
| Poll เป็น read-only | `poll()` ไม่เปลี่ยน local revision/state; covered by `test_external_decision_lifecycle.py` | PASS |
| Audit hash chain | `LifecycleEvent`, `_event_hash()` และ `audit_chain_valid()` | PASS |
| Snapshot defensive copy | `snapshot()` คืน deepcopy; mutation test ไม่เปลี่ยน private state | PASS |
| No-self-authorization | status flags ทุกตัวเป็น `False`, external/runtime authority เป็น `NONE` | PASS |
| No network/provider/scheduler side effect | AST gate scan ใน `test_external_decision_lifecycle_phase_end_hardening.py` | PASS |
| Private-key block scan | phase-end gate scan ของ repository text artifacts | PASS |

## 4. ผลการทดสอบ

การตรวจรอบนี้ใช้ test script สองชั้นตาม hardening policy: focused/adversarial suite และ phase-end hardening gate

| Test/gate | ขอบเขต | ผล |
|---|---|---|
| `test_external_decision_lifecycle.py` | initialization, expiry boundary, revoke, resubmission, reopen, remote update, stale/future poll, authority rejection, snapshot isolation, timezone/TTL validation | PASS |
| `test_external_decision_lifecycle_phase_end_hardening.py` | rerun focused suite, AST side-effect scan, authorization state lock, runtime boundary assertions, audit schema, private-key scan, `git diff --check` | PASS |
| `export_external_decision_lifecycle.py` | blank-safe lifecycle template snapshot และ deterministic record-template hash | พร้อมรันใน freeze step |

ผลดังกล่าวเป็น **functional verification passed ของ software evaluator** เท่านั้น ไม่ใช่หลักฐานว่า external authority ได้อนุมัติ, reviewer ได้รับแต่งตั้ง, signature ได้รับการยืนยัน หรือระบบ clinical/production ได้รับอนุญาต

## 5. Current local snapshot state

| Field | Value |
|---|---|
| Snapshot kind | `EXTERNAL_DECISION_LIFECYCLE_TEMPLATE` |
| Lifecycle template state | `LIFECYCLE_TEMPLATE_PENDING_EXTERNAL_RECORD` |
| Lifecycle instantiated | `false` |
| Record template status | `DECISION_RECORD_TEMPLATE` |
| Record template evidence class | `LOCAL_TEMPLATE` |
| External decision verified | `false` |
| Authorization promoted | `false` |
| External execution authorized | `false` |
| Clinical validation authorized | `false` |
| Production authorized | `false` |
| External authority | `NONE` |
| Independent reviewer | `NOT_STARTED` |
| Pilot gate | `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION` |

## 6. External evidence ที่ยังต้องมีจริง

ก่อนใช้ decision lifecycle เพื่อสนับสนุนการตัดสินใจภายนอก ต้องได้รับและตรวจสอบหลักฐานจาก boundary ภายนอกอย่างอิสระ ได้แก่ named external authority, independent reviewer appointment, conflict declaration, scope/window approval, manifest hash ที่ตรวจตรงกับ submission, decision basis, expiry, rollback/stop authority, signature/certificate/trust-chain custody, independent read-back และ revocation/supersession path

Evaluator นี้ **ไม่สร้างหลักฐานดังกล่าวขึ้นเอง** และไม่อนุญาตให้ local operator เปลี่ยน flag เพื่อข้ามขั้นตอน เมื่อไม่มีหลักฐานหรือผลตรวจยังค้างอยู่ สถานะต้องคง `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`

## 7. Stop conditions และ rollback

ต้องหยุดและคง fail-closed เมื่อพบ decision ID หรือ submission mismatch, record schema ไม่ตรง, expiry หรือ timestamp ไม่ปลอดภัย, stale/future response, revision ลดลง, event hash mismatch, actor role ไม่ถูกต้อง, opaque reference มี raw identity/secret, authorization flag ถูก promote, หรือ transition อยู่นอก registry

Rollback ทำได้โดย revert lifecycle module, tests, phase-end gate, exporter, report และ master registration จากนั้น rerun focused suite, phase-end gates, master regression และ release-freeze alignment ให้ครบอีกครั้ง

## 8. Claim boundary

ผลนี้สนับสนุนการอ้างได้เพียงว่าโครงการมี **controlled production prototype**, **functional verification passed** สำหรับ lifecycle evaluator, **pilot-ready foundation** ในมิติของ software controls และ **clinical validation pending**

ห้ามอ้างจากผลชุดนี้ว่าเป็น `clinical-ready`, `production-ready`, `tamper-proof`, `HIPAA/PDPA compliant 100%`, ได้รับ external authorization แล้ว หรือผ่านการทดสอบจริงบน hardware/clinical workflow แล้ว

## 9. Evidence paths

- `external_decision_lifecycle.py`
- `test_external_decision_lifecycle.py`
- `test_external_decision_lifecycle_phase_end_hardening.py`
- `export_external_decision_lifecycle.py`
- `EXTERNAL_DECISION_LIFECYCLE_READINESS_REPORT_20260821.md`
- `external_decision_record.py`
- `EXTERNAL_AUTHORIZATION_API_DECISION_LIFECYCLE.md`
- `EXTERNAL_DECISION_RECORD_READINESS_REPORT_20260821.md`
- `WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md`
- `WAVE_E_EXECUTION_PREFLIGHT_READINESS_REPORT_20260821.md`

## 10. Next controlled action

สร้าง local template snapshot ลงใน `evals/micro_rag/evidence/` จาก exporter, commit และ push revision ที่ตรวจสอบได้, refresh release freeze ให้ source revision ชี้ไปยัง commit ก่อนหน้าอย่างถูกต้อง แล้วรัน master regression รอบสุดท้าย ทั้งหมดนี้ไม่เปลี่ยน authorization boundary และไม่เริ่ม Wave E หรือ clinical validation
