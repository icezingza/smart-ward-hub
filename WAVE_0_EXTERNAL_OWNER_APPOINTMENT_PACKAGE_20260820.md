# Wave 0 External Owner Appointment Package

**Package state:** `READY_FOR_OWNER_APPOINTMENT`
**External execution:** `NOT_STARTED`
**Evidence class:** `SOFTWARE_VERIFIED/SIMULATION_ONLY` until external records are submitted and independently verified

## Purpose and boundary

เอกสารนี้ใช้แต่งตั้งผู้รับผิดชอบและรับข้อมูลอนุมัติก่อนเปิด isolated non-production validation ของ Smart Ward Hub เท่านั้น ไม่ใช่คำสั่งเปิดระบบ, ไม่ใช่ clinical authorization และไม่ใช่ production approval

> Local code ห้ามสร้าง `AUTHORIZED_BY_EXTERNAL_OWNER` และห้ามเปลี่ยน `external_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false`, `runtime_authority=NONE` หรือ `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.

## Required owner roles

| Role | หน้าที่ | หลักฐานที่ต้องส่ง |
|---|---|---|
| External coordinator | ประสาน package, scope, window และ evidence intake | opaque actor/org/appointment refs |
| Clinical owner | รับรอง protocol, clinical stop และ manual fallback | clinical appointment + scope approval ref |
| Security owner | รับรอง IdP/mTLS/ACL และ security stop | security appointment + test-tenant refs |
| Integration owner | รับรอง HIS/Admission sandbox contract | integration appointment + endpoint/ACL refs |
| Custody owner | รับรอง Device Trust, key issuance/rotation/revocation | custody appointment + ceremony/read-back refs |
| Reliability owner | รับรอง Acer bench, backup/restore, power-loss และ rollback | reliability appointment + drill refs |
| Independent verifier | ตรวจ hash, signature/read-back, chain-of-custody และ result integrity | independent appointment + verification channel |
| Stop authority | มีอำนาจหยุด test/deployment ทันทีเมื่อ stop condition เกิด | stop appointment + notification route |
| Rollback owner | อนุมัติ target revision และนำ restore/rollback drill | rollback appointment + restore evidence |

ทุก role ต้องใช้ **opaque references** เท่านั้นใน machine-readable intake ห้ามส่งชื่อจริง, อีเมล, เบอร์โทร, HN, patient data, private key หรือ secret ลง repository

## Required submission sequence

1. External coordinator ส่ง `OWNER_APPOINTMENT_TEMPLATE` ที่กรอก role refs ครบและไม่ซ้ำกัน
2. ทุก role ลงนาม scope ซึ่งระบุ in-scope/out-of-scope, environment, data boundary, allowed commands และ prohibited actions
3. ผู้มีอำนาจอนุมัติ test window แบบ timezone-aware พร้อม allowlist และ expiry
4. Stop authority และ rollback owner ยืนยัน stop rules, notification path, target revision, restore drill และ RPO/RTO
5. Security/integration owners ส่ง non-production IdP/HIS tenant, certificate chain/rotation plan และ network ACL evidence
6. Custody owner ส่ง dual-control ceremony, key custody/read-back และ revocation distribution plan
7. Reliability owner ส่ง Acer fixture/loopback readiness และแต่งตั้ง independent physical witness
8. Evidence custodian ส่ง manifest/hash/custody reference; independent verifier ตรวจ package ก่อนเปลี่ยนเป็น `READY_FOR_EXTERNAL_EXECUTION`

## Intake acceptance rules

Package จะถูก `REJECTED` หรือคง `BLOCKED` หากพบ unknown fields, raw identity/contact data, naive timestamps, duplicate roles, role collision, missing signed scope, missing test-window approval, missing stop/rollback owner, missing custody/read-back, production endpoint/credential, patient data หรือ authorization flag ที่เป็น true

Package จะเปลี่ยนเป็น `READY_FOR_EXTERNAL_EXECUTION` ได้ต่อเมื่อ:

- owner roles ครบและ separation of duties ผ่าน;
- signed scope, approved test window, allowlist และ expiry ผ่าน;
- non-production endpoint/IdP/mTLS/ACL references ผ่าน;
- key-custody and revocation read-back ผ่าน;
- Acer loopback fixture และ physical witness ผ่าน;
- backup/restore and rollback evidence ผ่าน;
- manifest SHA-256, redaction และ chain-of-custody ผ่าน;
- independent verifier ลงนามรับ package; และ
- authorization boundary ยัง locked และ external execution flag ยังถูกเปิดได้เฉพาะโดย external decision ที่มีหลักฐานจริง ไม่ใช่ local code

## Stop conditions

หยุดทันทีเมื่อพบ identity/certificate mismatch, untrusted response, unknown commit, audit-integrity failure, raw PII, secret leakage, key-custody mismatch, failed restore, WAL/disk failure, alert/manual fallback failure, unauthorized network exposure, scope/window expiry หรือ clinical stop request

## Machine-readable artifacts

- Validator: `wave0_owner_appointment_intake.py`
- Regression: `test_wave0_owner_appointment_intake.py`
- Exporter: `export_wave0_owner_appointment_intake.py`
- Template: `evals/micro_rag/evidence/wave0-owner-appointment-intake-template-20260820.json`
- Schema: `evals/micro_rag/evidence/wave0-owner-appointment-intake-schema-v1.json`

Current state remains `READY_FOR_OWNER_APPOINTMENT`; this package does not claim that any external role has actually been appointed.
