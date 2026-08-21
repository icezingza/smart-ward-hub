# Sync/Alert Replay Harness Readiness Report

**วันที่:** 22 สิงหาคม 2026

**สถานะ:** `SOFTWARE_VERIFIED` / `FIXTURE_ONLY_SIMULATION`

**Product status:** `NOT_PRODUCTION_READY`

**Pilot status:** `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`

## สรุปผล

Smart Ward Hub มี fixture-only replay harness สำหรับจำลองวงจร sync และ roaming snapshot โดยไม่แตะฐานข้อมูลจริง ไม่ส่งข้อมูลออกนอกเครื่อง และไม่เปลี่ยน runtime state. Harness ครอบคลุม retryable sync, retry exhaustion/dead-letter, explicit dead-letter replay confirmation, duplicate acknowledgment, acknowledgment bundle mismatch, partial sync write และ stale/future/current snapshot revision.

Harness แยกชัดเจนระหว่าง **replay eligibility** กับ **replay execution**. แม้ decision จะคืน `SOFTWARE_REPLAY_ELIGIBLE` หรือ `SOFTWARE_RESUME_ELIGIBLE` ในบางกรณี ก็ยังคง `replay_executed=false`, `mutation_performed=false`, `purge_executed=false` และ `external_transmission_performed=false` เสมอ

> ผลนี้เป็น **functional verification passed** ใน fixture-only software simulation เท่านั้น ไม่ใช่ evidence จาก HIS/EMR จริง, ward จริง, BMAX จริง หรือ clinical workflow จริง

## Contract ที่ตรวจ

| Scenario | Harness behavior | Resume/replay outcome |
|---|---|---|
| Retryable sync | เก็บ bundle ไว้ใน retry boundary | `SYNC_RETAINED_FOR_RETRY`, ไม่ resume |
| Retry limit exceeded | จัดประเภท dead-letter | `SYNC_DEAD_LETTER`, reconciliation required |
| Dead-letter replay without confirmation | หยุดไว้ที่ operator boundary | `DEAD_LETTER_REPLAY_CONFIRMATION_REQUIRED` |
| Dead-letter replay with confirmation | ให้ software replay eligibility | `DEAD_LETTER_REPLAY_ELIGIBLE`, ไม่ execute |
| First structured acknowledgment | ตรวจ bundle identity และ committed marker | `ACKNOWLEDGMENT_COMMITTED` |
| Duplicate acknowledgment | คืนผล idempotent และไม่ purge ซ้ำ | `IDEMPOTENT_ACK_REPLAY` |
| Ack bundle mismatch | ปฏิเสธก่อน mutation | `ACK_BUNDLE_ID_MISMATCH` |
| Partial sync write | ตรวจพบ purge/synced marker ไม่สอดคล้อง | `PARTIAL_SYNC_WRITE_DETECTED` |
| Stale snapshot | บังคับ refresh จาก authoritative Fixed Hub | `STALE_SNAPSHOT_REFRESH_REQUIRED` |
| Future snapshot revision | ปฏิเสธ client cursor ที่เชื่อถือไม่ได้ | `FUTURE_SNAPSHOT_REVISION` |
| Current snapshot | ไม่ต้อง refresh และไม่ mutation | `SNAPSHOT_CURRENT` |

## ความสัมพันธ์กับ implementation จริง

Handover sync endpoint ใน `main.py` ใช้ structured acknowledgment, bundle identity binding, idempotent replay เมื่อ `record.synced` แล้ว และเก็บ aggregate ไว้เมื่อ remote acknowledgment ไม่สำเร็จ. Roaming snapshot ใช้ revision ที่คำนวณจาก beds, sessions, unresolved alerts และ admission tasks; snapshot ที่ `since_revision` ตรงกับ authoritative revision จะคืน `unchanged=true`, ขณะที่ command ที่ revision เก่าจะถูกปฏิเสธด้วย stale revision contract

Harness นี้ไม่ได้เรียก endpoint เหล่านั้นโดยตรง เพราะจุดประสงค์คือ fault-injection และ state-replay isolation. จึงไม่ควรตีความว่าเป็นการยืนยัน database transaction, SQLite WAL behavior หรือ HIS/EMR transaction จริง

## Evidence และ redaction

`sync_alert_replay_harness.py` เป็น pure evaluator ที่รับ immutable fixture และคืน immutable decision. Identifier ของ bundle/snapshot ถูก validate ว่าเป็น opaque reference และถูกส่งออกเป็น digest ที่ไม่เผย raw reference. `export_sync_alert_replay.py` สร้าง machine-readable evidence พร้อม hash-chained replay transcript และ source-revision binding

Phase-end gate ตรวจว่า:

- ไม่มี network/provider/scheduler import
- ไม่มี production, clinical หรือ runtime authorization self-grant
- ไม่ execute replay, purge หรือ snapshot refresh
- transcript hash-chain ตรวจสอบได้
- raw identity/secret/private-key markers ไม่ปรากฏใน evidence
- `git diff --check` ผ่าน

## Verification record

| Gate | Result | Evidence |
|---|---|---|
| Focused/adversarial suite | PASS | `test_sync_alert_replay_harness.py` |
| No network/provider/scheduler side effect | PASS | `test_sync_alert_replay_harness_phase_end_hardening.py` |
| Duplicate acknowledgment safety | PASS | Focused test + matrix row |
| Partial write detection | PASS | Focused test + matrix row |
| Dead-letter classification/replay confirmation | PASS | Focused tests + matrix rows |
| Stale/future/current snapshot handling | PASS | Focused tests + matrix rows |
| Authorization boundary | PASS | Phase-end gate |
| Redaction/private-key scan | PASS | Phase-end gate |
| Hash-chained transcript | PASS | Exporter + phase-end gate |
| Master regression | Pending until commit/freeze refresh | `run_all_tests.py` |

## Claim boundary

ผลรองรับเฉพาะคำว่า **controlled production prototype**, **functional verification passed**, **pilot-ready foundation** และ **clinical validation pending**. ห้ามยกระดับเป็น clinical-ready, tamper-proof, HIPAA/PDPA compliant 100% หรือ production-ready

ยังไม่ยืนยัน:

1. HIS/EMR acknowledgment, retry and reconciliation บนระบบโรงพยาบาลจริง
2. SQLite/WAL partial transaction recovery ใน target host จริง
3. External dead-letter queue, worker lease และ durable replay execution
4. Network outage, TLS/OIDC/mTLS และ provider response authenticity
5. Clinical escalation, nurse workflow และ alarm fatigue response
6. BMAX roaming UI และ Fixed Hub authority arbitration บนอุปกรณ์จริง
7. External forensic anchor, trusted timestamp และ independent reviewer decision

## Authorization boundary

```json
{
  "external_authority": "NONE",
  "clinical_validation_authorized": false,
  "production_authorized": false,
  "runtime_authority": "NONE",
  "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
}
```

## ไฟล์หลัก

- `sync_alert_replay_harness.py`
- `test_sync_alert_replay_harness.py`
- `test_sync_alert_replay_harness_phase_end_hardening.py`
- `export_sync_alert_replay.py`
- `main.py` — handover sync and roaming snapshot implementation
- `models.py` — `HandoverRecord`, `SyncAttempt`, `RoamingCommand`, `Alert`, `WardSession`
- `schemas.py` — structured handover acknowledgment contract

## งานถัดไปภายใน

หลัง workstream นี้ ควรจัดทำ **durable worker replay contract** บน SQLite fixture-only target เพื่อเชื่อม dead-letter classification เข้ากับ bounded worker lease, restart reconciliation และ queue backup โดยยังคงไม่เปิด external transmission, clinical mutation หรือ production runtime authority
