# P4 Independent Reviewer Appointment Plan

**โครงการ:** Smart Ward Hub Reconcile
**วันที่:** 22 สิงหาคม 2026
**สถานะปัจจุบัน:** `P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_READY`
**ขอบเขต:** แผนและ internal preparation สำหรับการแต่งตั้ง Independent Reviewer; ยังไม่มีการแต่งตั้งหรือส่งหลักฐานภายนอก

## 1. วัตถุประสงค์และขอบเขต

แผนนี้กำหนดขั้นตอนจาก local reviewer preflight ไปสู่การแต่งตั้ง Independent Reviewer อย่างมีการควบคุม โดยแบ่งสิ่งที่ repository ทำได้ออกจากสิ่งที่ต้องดำเนินการโดย external authority, reviewer, hospital governance และ evidence custodian

Independent Reviewer มีหน้าที่ตรวจสอบหลักฐานและความสอดคล้องของ package อย่างเป็นอิสระ ไม่ใช่ผู้อนุมัติ production, clinical validation หรือ runtime authority และไม่ควรเป็นบุคคลเดียวกับผู้ปฏิบัติการระบบ, external coordinator หรือ evidence custodian

## 2. สถานะตั้งต้นจาก P4

| รายการ | สถานะหลักฐาน |
|---|---|
| Reviewer preflight | `P4_INDEPENDENT_REVIEWER_HANDOFF_READY` |
| Appointment plan | `P4_INDEPENDENT_REVIEWER_APPOINTMENT_PLAN_READY` |
| Reviewer appointment | `PENDING_EXTERNAL_APPOINTMENT` |
| Appointment decision | `NOT_ISSUED` |
| Submission status | `NOT_SUBMITTED` |
| Independent review | `NOT_STARTED` |
| Preflight checklist | 12 รายการ |
| Artifact mapping | 22 artifacts / 12 mappings |
| External Gates | 7 BLOCKED / 3 OPEN / 0 EVIDENCE_SUBMITTED |
| External authority | `NONE` |
| Clinical validation | `PENDING` |
| Production authorization | `false` |
| Runtime authority | `NONE` |

## 3. ขั้นตอนดำเนินงานตามลำดับ

### ขั้นที่ 0 — Local pre-appointment gate

**สถานะ:** ดำเนินการแล้วใน repository

ตรวจ schema, 12-item reviewer checklist, 22 artifact bindings, 12 pending external inputs, Zero-PII/redaction, release-freeze binding และ P4 blocked-gate dependency. ผลที่ยอมรับได้คือพร้อมสำหรับการแต่งตั้ง reviewer เท่านั้น โดยยังคง `ready_for_external_review=false` และ `submission_allowed=false`

หลักฐาน: `p4_independent_reviewer_handoff_readiness.py`, `p4_independent_reviewer_appointment_plan.py` และ evidence snapshots ที่เกี่ยวข้อง

### ขั้นที่ 1 — แต่งตั้ง external authority และกำหนด decision scope

**ผู้ดำเนินการ:** external authority / hospital governance

ต้องระบุผู้มีอำนาจแต่งตั้ง, องค์กร, decision scope, intended use, expiry, rollback และ stop authority โดยมี signed/read-back record. Scope ต้องครอบคลุม GV-01 ถึง GV-10 และ T-01 ถึง T-12 ในฐานะรายการตรวจสอบ ไม่ได้อนุญาตให้ reviewer ตัดสินใจรักษาผู้ป่วยหรือเปิด production

**หลักฐานบังคับ:** `appointing_authority_ref`, `decision_scope_ref`, `signed_scope_ref`, `expiry_ref`, `owner_approval_ref`

### ขั้นที่ 2 — คัดเลือก reviewer และตรวจ conflict/independence

**ผู้ดำเนินการ:** appointing authority และ reviewer candidate

ต้องบันทึก reviewer organization, independence statement และ conflict declaration. Reviewer ต้องแตกต่างจาก internal operator, external coordinator และ evidence custodian และต้องไม่มีอำนาจ self-appointment หรือ self-approval

**หลักฐานบังคับ:** `reviewer_appointment_ref`, `reviewer_organization_ref`, `conflict_declaration_ref`, `appointment_ref`

ห้ามใส่ชื่อจริง, อีเมล, เบอร์โทรศัพท์ หรือข้อมูลส่วนบุคคลลงใน local evidence snapshot. ให้ใช้ opaque reference ที่ผูกกับระบบ custody ที่ได้รับอนุมัติแทน

### ขั้นที่ 3 — กำหนด role separation และ stop/recovery authority

**ผู้ดำเนินการ:** external authority ร่วมกับ operations/reliability owner

ต้องกำหนดบทบาทอย่างน้อย ได้แก่ independent reviewer, appointing authority, internal operator, evidence custodian, stop authority และ rollback owner. Stop authority กับ rollback owner ต้องเป็นคนละ role และต้องกำหนด incident channel กับ recovery approver โดย reviewer ไม่มีสิทธิ์ bypass stop rule

**หลักฐานบังคับ:** role appointment references, `stop_rule_ref`, `notification_ref`, `rollback_plan`, `restore_drill_ref`

### ขั้นที่ 4 — เตรียม evidence custody และ independent read-back

**ผู้ดำเนินการ:** evidence custodian และ independent reviewer

ต้องกำหนด custody path, submission manifest reference, read-back channel และวิธีตรวจ release-freeze source กับ artifact SHA-256. Reviewer ต้องสามารถตรวจ package ที่ถูก freeze ได้โดยไม่แก้ไข application/runtime state

**หลักฐานบังคับ:** `submission_manifest_ref`, `custody_ref`, freeze source/hash read-back, local artifact hash read-back และ redaction result

### ขั้นที่ 5 — ออก appointment record

**ผู้ดำเนินการ:** appointing authority

เมื่อ conflict declaration, scope, role separation, custody และ stop/rollback records ครบ จึงออก signed appointment record. การออก appointment record เป็น external action และต้องทำผ่านช่องทางที่ผู้มีอำนาจกำหนด ไม่ใช่การแก้ JSON ใน repository โดยตรง

**เงื่อนไขผ่าน:** `reviewer_appointment` เปลี่ยนได้จาก `PENDING_EXTERNAL_APPOINTMENT` เฉพาะเมื่อมี external signed/read-back record; `appointment_decision` ต้องมี evidence อ้างอิงและยังไม่เปลี่ยน external/clinical/production authority

### ขั้นที่ 6 — Reviewer acceptance และเปิด review session

**ผู้ดำเนินการ:** appointed Independent Reviewer

Reviewer ต้องยืนยันการรับ appointment, scope, expiry, conflict status, custody path และ stop/recovery rules จากนั้นจึงเปิด review session ตาม protocol. ต้องมี session ID, dossier ID, opened timestamp และ audit trail ที่ไม่เปิดเผย raw identity

**เงื่อนไขก่อนเปิด session:** appointment accepted, scope signed, custody/read-back available, freeze source verified, checklist accessible และ reviewer ไม่มี prohibited authority

### ขั้นที่ 7 — Independent evidence review

Reviewer ตรวจ IRP-01 ถึง IRP-12, GV-01 ถึง GV-10 และ T-01 ถึง T-12 ตาม dossier. ผลลัพธ์ที่อนุญาตคือ accepted for review, requires clarification, blocked external evidence หรือ rejected ตาม evidence จริง ไม่ใช่การเปลี่ยนเป็น production-ready โดยอัตโนมัติ

Reviewer ต้องบันทึก finding, severity, outcome, evidence references, timestamp และ residual-risk owner. หากพบความเสี่ยงด้าน clinical, privacy, security, hardware หรือ external custody ต้องหยุดตาม stop rule และเปิด remediation loop

### ขั้นที่ 8 — Close review และออก decision record

เมื่อ reviewer ตรวจครบ ต้องมี independent read-back และ signed decision record. Decision record ต้องแยกชัดเจนระหว่าง evidence accepted, unresolved findings, residual risk, external authorization และ clinical/production status

หากยังไม่มี external authorization ให้สถานะเป็น closed-no-authorization หรือ blocked ตามหลักฐาน ห้ามใช้ผล review ภายในเพื่อ self-authorize pilot, production หรือ clinical validation

## 4. สิ่งที่ต้องเตรียมก่อนส่งให้ผู้แต่งตั้ง reviewer

| รายการ | ทำได้ภายใน | ต้อง external |
|---|---:|---:|
| ตรวจ schema/checklist/artifact mapping | ได้ | ไม่ใช่การอนุมัติ |
| สร้าง appointment packet template | ได้ | ไม่ใช่ appointment record |
| กำหนด scope draft และ out-of-scope | ได้ | ต้อง signed โดย authority |
| เตรียม role-separation rules | ได้ | ต้องแต่งตั้ง role จริง |
| Redaction/Zero-PII scan | ได้ | ต้อง independent read-back |
| Freeze/hash manifest | ได้ | ต้อง reviewer verify |
| ระบุ reviewer ตัวจริง | ไม่ได้ | ต้อง external appointment |
| Conflict declaration | ไม่ได้ | reviewer/authority ต้องลงนาม |
| Custody path ที่มีผลจริง | ไม่ได้ | evidence custodian/authority |
| Review acceptance/findings | ไม่ได้ | independent reviewer |
| Clinical/production authorization | ไม่ได้ | external governance |

## 5. เงื่อนไข fail-closed

ระบบต้องคง `NOT_ISSUED`, `NOT_SUBMITTED`, `NOT_STARTED`, `ready_for_external_review=false` และ `submission_allowed=false` หากยังไม่มี signed appointment record. หากมีการแก้ scope, role, reviewer status, production flag, clinical flag, custody reference หรือ freeze binding โดยไม่มีหลักฐานที่ตรงกัน ให้หยุดและคืน blocked decision

ห้ามใช้ local software evidence เพื่อเปลี่ยน external authority, clinical validation authority, production authority หรือ runtime authority. ห้ามส่งข้อมูลภายนอกอัตโนมัติจาก exporter และห้ามใส่ raw patient identifier, reviewer contact หรือ secret material ใน evidence snapshot

## 6. ขอบเขต residual risk

แผนนี้ยังไม่สร้างหลักฐานของ reviewer appointment จริง, conflict declaration จริง, hospital governance, real IdP/HIS/mTLS, hardware validation, manufacturer key custody, external WORM/trusted timestamp หรือ clinical validation. External Gates ยังคง 7 BLOCKED / 3 OPEN / 0 PASSED

> การผ่านของ P4 appointment plan หมายถึงเอกสารและ control สำหรับเริ่มกระบวนการแต่งตั้งพร้อมแล้วเท่านั้น ไม่ใช่การแต่งตั้ง reviewer และไม่ใช่ authorization ใด ๆ

## 7. Repository evidence

- `p4_independent_reviewer_appointment_plan.py`
- `export_p4_independent_reviewer_appointment_plan.py`
- `test_p4_independent_reviewer_appointment_plan.py`
- `test_p4_independent_reviewer_appointment_plan_phase_end_hardening.py`
- `p4_independent_reviewer_handoff_readiness.py`
- `evals/micro_rag/evidence/p4-independent-reviewer-appointment-plan-local.json`
- `evals/micro_rag/evidence/p4-independent-reviewer-handoff-readiness-local.json`
- `wave0_owner_appointment_intake.py`
- `independent_reviewer_readiness_preflight.py`

สถานะผลิตภัณฑ์ยังเป็น `CONTROLLED_PRODUCTION_PROTOTYPE` และ `NOT_PRODUCTION_READY`
