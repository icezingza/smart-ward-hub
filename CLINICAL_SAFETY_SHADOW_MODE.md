# Smart Ward Hub — Clinical Safety and Shadow-Mode Protocol

**Status:** Draft for clinical governance review  
**Use:** Planning artifact only; not a clinical order, diagnosis, or treatment protocol.

> I'm an AI, not a medical professional — treat this as informed analysis, not a medical diagnosis; a qualified clinician should confirm anything consequential.

## 1. Purpose and safety principle

ช่วง Shadow Mode ระบบจะคำนวณ safety signal จาก telemetry แต่จะไม่เป็นผู้วินิจฉัย ไม่แทนที่ vital-sign measurement ที่โรงพยาบาลกำหนด และไม่สั่งการรักษา พยาบาลและแพทย์ยังคงใช้ observation, clinical assessment และ protocol ของโรงพยาบาลเป็นหลัก

การแจ้งเตือนของระบบต้องใช้คำว่า **suspected fall**, **vital anomaly signal** หรือ **device/perimeter warning** แทนคำวินิจฉัย ระบบต้องแสดงเวลาที่รับข้อมูล, อายุข้อมูล, อุปกรณ์, เตียง, confidence/heuristic context ที่เปิดเผยได้ และสถานะว่าเป็น signal จากระบบ

## 2. Shadow-mode workflow

```text
Telemetry → Edge validation → Local signal evaluation → Shadow record
        → Independent clinical observation → Reviewer classification
        → Daily safety review → Threshold/change-control decision
```

ในช่วงแรกไม่ควรเปิดเสียงหรือ push notification ที่เปลี่ยน workflow จริงโดยไม่ได้รับอนุมัติจาก clinical governance หากมีการเปิดแสดงผล ต้องแยกป้ายกำกับให้ผู้ใช้เห็นชัดว่าเป็น shadow signal และต้องมีช่องทางรายงาน false alarm หรือ missed event

## 3. Event review categories

| Category | Definition | Required reviewer action |
|---|---|---|
| True positive | Signal สอดคล้องกับเหตุการณ์ที่ยืนยันได้ | บันทึกเวลาและหลักฐานประกอบ |
| False positive | Signal เกิดแต่ไม่พบเหตุการณ์ตามเกณฑ์ review | ระบุสาเหตุที่เป็นไปได้ |
| Missed event | พบเหตุการณ์จาก observation แต่ระบบไม่ส่ง signal | เปิด safety incident review |
| Indeterminate | หลักฐานไม่พอหรือเวลาไม่ตรงกัน | ขอข้อมูลเพิ่มหรือจัดเป็น unresolved |
| Device/data fault | สาเหตุหลักมาจากอุปกรณ์ แบตเตอรี่ clock หรือ network | แยกเป็น technical incident |

## 4. Minimum review dataset

ต้องใช้ข้อมูลที่ de-identify แล้วสำหรับการวิเคราะห์ โดยเก็บเฉพาะ pseudonymous patient token, device, bed context ที่จำเป็น, event time, received time, alert state, reviewer classification และเหตุผลที่บันทึก การส่งออกเพื่อวิเคราะห์ต้องไม่รวมชื่อ, HN, ที่อยู่ หรือข้อมูลระบุตัวบุคคลที่ไม่จำเป็น

## 5. Safety metrics

| Metric | วิธีคำนวณ | หมายเหตุ |
|---|---|---|
| Signal rate | จำนวน signal ต่อ patient-hour/device-hour | ใช้ดู alarm burden |
| Confirmed-event rate | true positive / signal ทั้งหมด | ต้องกำหนด denominator ให้ชัด |
| Missed-event count | จำนวนเหตุการณ์ที่ไม่มี signal | ต้อง review แยกตาม data availability |
| Acknowledge time | เวลารับทราบ - เวลาเปิด alert | ไม่ใช่ clinical response time โดยอัตโนมัติ |
| Resolve time | เวลาปิดเหตุการณ์ - เวลาเปิด alert | ต้องระบุว่าใครเป็นผู้ปิด |
| Data freshness | เวลา review - received_at | แยก device/network delay |
| False-positive review rate | จำนวน signal ที่ review แล้ว / signal ทั้งหมด | ต้องไม่สรุป accuracy หากยัง review ไม่ครบ |

## 6. Stop conditions

ต้องหยุดหรือย้อนกลับ Shadow Mode หากพบ critical privacy leakage, identity mismatch, duplicate active pairing, telemetry sequence corruption, persistent database recovery failure, alert flood ที่ทำให้ workflow ใช้งานไม่ได้, missed event ที่มีความรุนแรง, FHIR sync ลบข้อมูลก่อน acknowledgment หรือบุคลากรใช้งาน signal เป็นคำสั่งรักษาโดยเข้าใจผิด

ทุก stop event ต้องมี incident ID, เวลา, device/ward scope, data affected, immediate containment, ผู้อนุมัติการกลับมาใช้งาน และ change record

## 7. Change control

การเปลี่ยน fall threshold, physiological threshold, risk weighting, deduplication window, battery/network policy หรือข้อความที่แสดงแก่บุคลากรต้องผ่าน review ก่อน deploy ต้องเก็บ version ของ algorithm/config, test result, reviewer, effective time และ rollback version

ห้ามปรับ threshold โดยอาศัย KPI เพียงอย่างเดียว หรือนำผลจาก synthetic data ไปอ้างแทนผลจากข้อมูลที่ผ่านการทบทวนทางคลินิก

## 8. Approval gates

ก่อนเริ่ม Shadow Mode ต้องมี clinical owner, technical owner, privacy/security reviewer, ward manager, incident contact, backup/restore evidence, device inventory, training note, data-retention decision และ rollback plan โดยทุกฝ่ายต้องรับทราบว่าเป็น decision-support prototype

การขยายไป Limited Pilot จะทำได้เมื่อมี daily review ที่สม่ำเสมอ, unresolved high-severity event ถูกจัดการ, data-quality metrics อยู่ในเกณฑ์, operator เข้าใจ alert lifecycle และ clinical governance ลงนามอนุมัติขอบเขตใหม่


## 9. Software contract implementation status

The planning protocol is now complemented by `clinical_shadow_mode.py`, `test_clinical_shadow_mode.py` and `P1_005_CLINICAL_SHADOW_MODE_CONTRACT.md`. These add deterministic software checks for governance-policy completeness, non-diagnostic signal labels, opaque-token boundaries, review categories, non-accuracy metrics and stop/resume controls.

This does not convert the document into a clinical protocol or approval. P1-005 remains pending named clinical ownership, governance sign-off, staff walkthrough, human-factors review, alarm-fatigue review, data-retention decision and real-world shadow-mode evidence.
