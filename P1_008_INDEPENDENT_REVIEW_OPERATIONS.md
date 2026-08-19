# P1-008 — Independent Review Operations & Controlled Pilot Gate

**สถานะ:** software baseline implemented; dry-run regression passed; independent review and clinical governance remain external

## 1. วัตถุประสงค์

P1-008 กำหนด operation contract สำหรับคณะกรรมการตรวจสอบอิสระหลังจากมี GV-10 dossier แล้ว โดยแยก **การรับหลักฐานเข้าตรวจ**, **การออก finding**, **การปิด review session** และ **การอนุมัติ Controlled Pilot** ออกจากกันอย่างเด็ดขาด

สคริปต์ `independent_review_operations.py` เป็น software contract สำหรับ review session เท่านั้น ไม่ใช่ระบบอนุมัติ clinical validation และไม่ใช่ระบบอนุมัติ production deployment

## 2. Review session lifecycle

| State/operation | เงื่อนไข | ผลลัพธ์ |
|---|---|---|
| `OPEN` | มี `session_id`, `dossier_id`, reviewer role และ timezone-aware timestamp | รับ evidence และออก finding ได้ |
| `accept_evidence(entry)` | `EvidenceEntry.validate()` ผ่าน, evidence ID ไม่ซ้ำ | บันทึก evidence พร้อม gate traceability |
| `issue_finding(finding)` | severity/outcome ถูกต้อง และอ้างถึง evidence ที่รับแล้วใน gate เดียวกัน | บันทึก finding ที่ตรวจสอบย้อนกลับได้ |
| `close()` | ต้องมี accepted evidence และ closed timestamp แบบมี timezone | ล็อก session ไม่ให้แก้ไขต่อ |
| หลัง `CLOSED` | ห้ามรับ evidence หรือ issue finding เพิ่ม | ต้องเปิด session ใหม่หรือใช้กระบวนการ change control ภายนอก |

## 3. Finding severity และ outcome

Severity ที่รองรับคือ `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` และ `INFO`. Outcome ที่รองรับคือ `ACCEPTED_FOR_REVIEW`, `REQUIRES_CLARIFICATION`, `BLOCKED_EXTERNAL_EVIDENCE` และ `REJECTED`

Finding ทุกตัวต้องมี `finding_id`, `gate_id`, summary ที่ไม่มี raw identity, evidence IDs อย่างน้อยหนึ่งรายการ, issued timestamp ที่มี timezone และบทบาทผู้ตรวจสอบ

## 4. Traceability contract

ระบบจะ reject finding หาก evidence ID ยังไม่ถูก accept ใน session, evidence อยู่คนละ gate กับ finding, evidence ID ซ้ำ, gate ID ไม่อยู่ใน GV-01 ถึง GV-10 หรือ evidence ถูกแก้ไขจนไม่ผ่าน GV-10 validator

โครงสร้างนี้ทำให้ reviewer เดินเส้นทางย้อนกลับได้:

> Finding → Evidence ID → Artifact Reference → SHA-256 / Chain-of-Custody → External Gate

## 5. No-authorization boundary

ค่าต่อไปนี้ถูกตรึงเป็น `False` และไม่มี method สำหรับเปิดสิทธิ์ภายใน software contract:

- `clinical_validation_authorized=False`
- `production_authorized=False`
- `real_world_authorization=False`

การเรียก `authorize_clinical_validation()` หรือ `authorize_production()` จะถูก reject และระบุว่าต้องใช้ external governance เท่านั้น

## 6. Acceptance evidence

- `independent_review_operations.py`
- `test_independent_review_operations.py`
- `GV10_INDEPENDENT_REVIEW_DOSSIER.md`
- `GV10_SUBMISSION_CHECKLIST.md`
- `GV10_SIMULATION_REPORT.md`

ผล test เป็น **software verification ของ review-operation contract** ไม่ใช่หลักฐานว่าคณะกรรมการอิสระได้ตรวจจริง หรือว่า external gate ใดผ่านแล้ว

## 7. เงื่อนไขก่อน Controlled Pilot Gate

ก่อนจะพิจารณา Controlled Pilot ต้องมีอย่างน้อย:

1. ผู้ตรวจสอบอิสระและ clinical owner ที่แต่งตั้งอย่างเป็นทางการ
2. Signed/read-only evidence export พร้อม manifest และ chain-of-custody
3. การ reproduce software tests และบันทึก findings ที่ปิดหรือยอมรับแล้ว
4. Real HIS/Admission, OIDC/mTLS, Acer host, serial/power-loss, WORM anchor และ device key-custody evidence ตาม gate ที่เกี่ยวข้อง
5. Clinical protocol, consent/waiver, training, manual fallback และ human-factors review
6. การตัดสินใจของ governance body ที่อยู่นอก software contract

**หลักการ:** ไม่มี external evidence ไม่ปิด gate; ไม่มี governance approval ไม่ทำ clinical validation
