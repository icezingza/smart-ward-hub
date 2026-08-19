# Smart Ward Hub — Pilot Readiness Pack

**สถานะเอกสาร:** Draft for controlled pilot planning  
**สถานะระบบ:** Controlled production prototype; clinical validation pending  
**เจ้าของเอกสาร:** Manus AI  
**วันที่:** 19 สิงหาคม 2026

> I'm an AI, not a medical professional — treat this as informed analysis, not a medical diagnosis; a qualified clinician should confirm anything consequential.

## 1. วัตถุประสงค์

เอกสารนี้กำหนดกรอบก่อนนำ Smart Ward Hub ไปทดสอบแบบควบคุมในโรงพยาบาล โดยมีเป้าหมายเพื่อเปลี่ยนระบบจาก functional software prototype ให้เป็น **pilot-ready foundation** ที่มีขอบเขตชัดเจน มีหลักฐานทดสอบ มีผู้รับผิดชอบ มี rollback plan และไม่ทำให้ระบบถูกนำไปใช้เป็นเครื่องมือวินิจฉัยโดยไม่ได้รับการทบทวนจาก clinical governance

Pilot นี้จะทดสอบการรับข้อมูลจาก wearable, การจับคู่เตียง, การประมวลผลที่ Edge, การแจ้งเตือนเพื่อสนับสนุนการตัดสินใจ, การทำงานเมื่อเครือข่ายขัดข้อง, การตรวจสอบข้อมูลย้อนหลัง และการส่งข้อมูลแบบ FHIR ในสภาพแวดล้อมที่แยกจาก production HIS จนกว่าจะผ่าน acceptance gates

## 2. Architecture Freeze

ในช่วง Pilot ห้ามเปลี่ยน contract หลักโดยไม่ผ่าน change control:

| ส่วน | Frozen decision | ขอบเขต |
|---|---|---|
| Identity | Edge เก็บ `patient_token` เท่านั้น | Mapping ไป HN/name อยู่ที่ HIS หรือ identity service ภายนอก |
| Telemetry | `TelemetryPacket v1` | ใช้ `schema_version`, `sequence`, `accel_x/y/z`, `battery_pct` และ UTC-normalized timestamp |
| Runtime | SQLite WAL + thread-safe bounded Edge store | Edge ทำงานต่อได้เมื่อ HIS/Internet ขัดข้อง |
| Authentication | Protected endpoint ต้องมี bearer token scope | Production ต้องยกระดับเป็น OAuth2/OIDC และ mTLS |
| Alert | Alert เป็น clinical decision-support signal | พยาบาล/แพทย์เป็นผู้ยืนยันและดำเนินการ |
| Evidence | Local SHA-256 chain เป็น tamper-evident layer | ยังไม่ใช่ tamper-proof หรือหลักฐานทางกฎหมายโดยอัตโนมัติ |
| Integration | FHIR Bundle + acknowledgment ก่อน purge | Sync failure ต้องเก็บข้อมูลไว้เพื่อ retry |

การเปลี่ยน schema, alert threshold, retention, FHIR mapping หรือ authentication policy ต้องบันทึกเหตุผล, risk impact, test evidence และผู้อนุมัติ

## 3. Trust Boundaries และ Threat Model

| Threat | ผลกระทบ | Control ที่ต้องมี | Evidence |
|---|---|---|---|
| อุปกรณ์ปลอมส่ง telemetry | ข้อมูลผิดและ alert ผิด | device registry, token/mTLS identity, sequence validation | unauthorized-device test |
| Replay หรือ packet ซ้ำ | สถิติและ alert ผิด | monotonic sequence, duplicate rejection, clock policy | 409 replay test |
| บุคคลเข้าถึง Hub | ข้อมูลและหลักฐานถูกขโมย | disk encryption, OS hardening, least privilege, secret manager | host-hardening checklist |
| PII หลุดใน cache/log | privacy breach | patient-token-only model, PII key guard, log redaction | grep/static scan + runtime test |
| Database/checkpoint ถูกแก้ | หลักฐานไม่น่าเชื่อถือ | local hash verification, external anchor, protected key custody | tamper test + anchor test |
| HIS sync ปลอม/ล้มเหลว | ข้อมูลหายหรือ purge ผิด | mTLS, OAuth2/OIDC, idempotency, acknowledgment gate | integration failure test |
| Power loss ระหว่างเขียน | telemetry หายหรือ DB เสีย | WAL, atomic checkpoint, backup/restore, recovery test | fault-injection report |
| Alert fatigue | พยาบาลเพิกเฉยต่อ alert | lifecycle, deduplication, acknowledge/resolve metrics | alarm review report |

## 4. TelemetryPacket v1 Contract

```json
{
  "schema_version": "1.0",
  "device_id": "MAC-A1:B2:C3:D4:E5:F6",
  "sequence": 42,
  "timestamp": "2026-08-19T10:00:00Z",
  "ppg": 0.82,
  "accel_x": 0.01,
  "accel_y": -0.02,
  "accel_z": 1.00,
  "skin_temp": 36.7,
  "battery_pct": 88.0,
  "heart_rate": 76.0,
  "spo2": 98.0
}
```

`sequence` ต้องเพิ่มขึ้นต่ออุปกรณ์และไม่สามารถย้อนกลับได้ภายใน lifecycle เดียวกันของ device identity หากรับ sequence ซ้ำหรือต่ำกว่าค่าล่าสุด ระบบต้องตอบ `409 duplicate_or_out_of_order_sequence` และไม่เขียน packet ลง buffer

หน่วยวัดและคุณภาพข้อมูลต้องติดตามใน device registry ต่อไป ได้แก่ sampling rate, firmware version, sensor calibration status, clock offset และ battery state ส่วน `timestamp` จากอุปกรณ์ใช้เป็น event time ขณะที่ `received_at` จาก Hub ใช้เป็น ingestion time

## 5. Data Governance และ Zero-PII

Edge Hub ห้ามเก็บหรือเขียนลง log ได้แก่ชื่อผู้ป่วย, HN, เลขบัตร, วันเกิด, ที่อยู่, เบอร์โทรศัพท์, patient mapping table หรือ PII ที่ไม่ได้ระบุใน contract หากต้องแสดงข้อมูลบน HIS ให้ใช้ `patient_token` ที่ HIS เป็นผู้สร้างและควบคุม mapping

ข้อมูลที่ต้องกำหนดเป็นลายลักษณ์อักษร ได้แก่ retention period ของ raw telemetry, aggregate, alert และ forensic package; สิทธิ์การอ่าน; การลบ; การสำรอง; การกู้คืน; การส่งออก; และกระบวนการ incident response การลบ PII ออกจาก Edge ไม่เพียงพอที่จะอ้างว่าองค์กร compliant โดยสมบูรณ์ ต้องตรวจสอบกระบวนการและระบบที่เกี่ยวข้องทั้งหมด

## 6. Acceptance Test Gates

| Gate | ต้องพิสูจน์อะไร | ผ่านเมื่อ |
|---|---|---|
| G1 — Contract | schema และหน่วยไม่คลุมเครือ | valid/invalid/legacy payload tests ผ่าน |
| G2 — Privacy | Edge ไม่เก็บ PII | model, cache, checkpoint, log scan ไม่พบ PII fields |
| G3 — Auth | endpoint ปิดเมื่อไม่มี identity | unauthenticated = 401/503, wrong scope = 403 |
| G4 — Reliability | restart/power/network fault | recover ตาม RTO/RPO ที่กำหนดและไม่ทำให้ DB เสีย |
| G5 — Performance | รับโหลดตาม pilot scope | มี p50/p95/p99, CPU/RAM/disk และ dropped-packet report |
| G6 — Alert | alert ส่งผลต่อ workflow ได้จริง | acknowledge/resolve/failure/duplicate tests ผ่าน |
| G7 — Integration | FHIR ไม่ทำให้ข้อมูลหาย | validation, retry, idempotency และ purge-after-ACK ผ่าน |
| G8 — Governance | ทีมปฏิบัติงานพร้อม | runbook, owner, escalation, rollback และ incident form พร้อม |

## 7. Clinical Safety และ Shadow Mode

ช่วงแรกต้องใช้ **shadow mode** โดยระบบคำนวณและบันทึก safety signal แต่ผลลัพธ์ไม่ถูกใช้แทนการประเมินของบุคลากรทางการแพทย์ พยาบาลจะเปรียบเทียบ signal กับ observation จริงและบันทึกผลว่า true positive, false positive, missed event หรือ indeterminate

ต้องกำหนด clinical review protocol ก่อนเก็บข้อมูล ได้แก่ inclusion/exclusion criteria, เหตุการณ์ที่ต้อง review, วิธี de-identification, วิธีจัดการ disagreement, เวลาในการ review, ผู้อนุมัติ และวิธีรายงาน adverse event ห้ามปรับ threshold เพื่อให้ KPI ดูดีโดยไม่มี change record และ clinical rationale

Fall detection, hypoxia signal และ risk weighting เป็น heuristic/decision-support logic จึงต้องประเมิน false positive และ false negative แยกจาก software uptime หรือ API latency ไม่ควรใช้ค่าเดียวสรุปว่า “ระบบแม่นยำ”

## 8. HIS/EMR Integration Contract

การเชื่อมต่อจริงต้องใช้ test tenant หรือ sandbox ก่อน โดยแต่ละ Bundle ต้องมี idempotency key, schema/profile version, pseudonymous subject reference, event window, source device metadata ที่อนุญาต และ signature/manifest หากอยู่ใน evidence workflow

Flow ที่ยอมรับได้คือ:

```text
Create Digest → Validate FHIR → Sign/Record Manifest → Send over mTLS
        → Receive verified acknowledgment → Mark synced → Purge eligible aggregates
```

หาก timeout, HTTP 4xx, HTTP 5xx, certificate failure หรือ response contract ไม่ผ่าน validation ระบบต้องเก็บ aggregate เดิมไว้ ตั้งสถานะ retry/dead-letter และแจ้ง operator ห้าม purge จากการได้รับค่า boolean ที่ไม่มีหลักฐานจากปลายทาง

## 9. Pilot Operations Runbook

ก่อนเริ่มแต่ละวัน operator ต้องตรวจ health/readiness, disk, database backup, checkpoint state, device registry, time synchronization, certificate/token expiry และ unresolved alerts เมื่อเกิด incident ให้บันทึกเวลา, device, alert, system state, operator action, data loss, recovery action และผลกระทบ

Rollback ต้องทำได้โดยหยุด ingestion อย่างปลอดภัย, รักษา forensic package, export audit log, restore known-good version/database backup และยืนยันว่าไม่มีการส่ง FHIR ซ้ำโดยไม่มี idempotency key การขยายจาก 5–10 เตียงไป 30–50 เตียงต้องได้รับอนุมัติจากผล gate ไม่ใช่จากเวลาที่ระบบรันได้นานเพียงอย่างเดียว

## 10. KPI ที่ควรเก็บแบบไม่สร้างความเข้าใจผิด

| หมวด | Metric |
|---|---|
| Reliability | uptime, restart recovery success, DB recovery, checkpoint recovery |
| Performance | packet/sec, p50/p95/p99 latency, CPU, RAM, disk, dropped samples |
| Data quality | duplicate rate, out-of-order rate, clock drift, missing field rate |
| Alert workflow | alert count, acknowledge time, resolve time, duplicate suppression, false-positive review |
| Integration | FHIR validation rate, sync success, retry count, dead-letter count, purge-after-ACK count |
| Safety | missed-event review, escalation compliance, operator override, adverse-event review |

ผล simulation ต้องติดป้ายว่า `software_functional_simulation` เสมอ และห้ามนำไปแทน hardware, clinical หรือ regulatory evidence

## 11. Exit Criteria สำหรับ Controlled Pilot

Pilot จะเริ่มได้เมื่อ G1–G4 ผ่าน, G5 มีผล load test บน environment ที่ใกล้เคียงจริง, G6–G7 มี owner และ rollback, G8 มีทีมรับผิดชอบครบ, security review ไม่พบ critical finding ที่ยังเปิดอยู่ และ clinical governance อนุมัติ shadow-mode protocol

Pilot จะขยายจำนวนเตียงได้เมื่อมีหลักฐานอย่างน้อยหนึ่งรอบของ daily review, incident review, data-quality review, alert-fatigue review, backup/restore test และ change-control review โดยไม่พบ unresolved high-severity risk ที่เกี่ยวกับผู้ป่วยหรือข้อมูลระบุตัวบุคคล

## 12. Non-claims

ระบบนี้ยังไม่ควรอ้างว่าเป็น medical device ที่ได้รับการรับรอง, ใช้แทนการวินิจฉัย, มีความแม่นยำ 100%, ป้องกันการแก้ไขหลักฐานได้โดยสมบูรณ์, compliant 100% หรือพร้อมใช้ใน production โดยอัตโนมัติ คำอธิบายที่เหมาะสมคือ **controlled production prototype with a pilot-ready foundation; clinical and regulatory validation pending**
