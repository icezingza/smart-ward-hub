# Smart Ward Hub — Operations Runbook

**สถานะ:** Draft for pilot operations review  
**ขอบเขต:** Edge Hub software operations; ไม่ใช่คำสั่งการรักษาพยาบาล

## Startup checklist

ก่อนเปิดระบบให้ตรวจสอบว่า service version ตรงกับ change record, `SW_AUTH_TOKENS_JSON` มาจาก secret store, `SW_ENABLE_DOCS=false` ใน pilot, allowed hosts ถูกต้อง, database path อยู่บน encrypted volume, checkpoint path มีสิทธิ์เฉพาะ service account และเวลาเครื่องตรงกับ trusted time source

จากนั้นตรวจ `/health`, database readiness, active device registry, disk capacity, backup freshness, certificate/token expiry, unresolved alerts และ FHIR sync queue หากข้อใดไม่ผ่าน ให้หยุดการขยายระบบและเปิด incident ก่อนรับ telemetry จริง

## Daily ward checks

| Check | Evidence | Owner |
|---|---|---|
| Device registry and pairing | active device/bed list | Ward operator |
| Data freshness | latest received timestamp and clock drift | Technical operator |
| Buffer pressure | buffered and dropped sample counters | Technical operator |
| Alert queue | OPEN/ACKNOWLEDGED/IN_PROGRESS items | Charge nurse |
| Sync queue | retry/dead-letter count | Integration owner |
| Backup | last successful backup and restore point | System owner |
| Security | auth failures, certificate/token expiry | Security owner |

## Incident response

เมื่อเกิดเหตุให้บันทึก incident ID, เวลาเริ่มต้น, scope ของ Ward/device, observed symptom, request ID, alert IDs, data affected และผู้ดำเนินการ ห้ามแก้ไข forensic package เดิมโดยตรง ให้สร้าง corrective record แยกและรักษา hash/manifest เดิมไว้

หากมี PII leakage, identity mismatch, database corruption, repeated missed event, FHIR purge error หรือ alert flood ให้หยุดการใช้งาน feature ที่เกี่ยวข้องทันที ใช้ manual clinical workflow ตามนโยบายโรงพยาบาล และแจ้ง clinical, security และ technical owners ตาม escalation matrix

## Backup and restore

ควร backup SQLite database, WAL checkpoint state, configuration version และ forensic manifest ตาม retention policy ที่ได้รับอนุมัติ โดยไม่ backup secret ในไฟล์เดียวกับฐานข้อมูล ต้องทดสอบ restore บนเครื่องแยกและตรวจ row count, hash verification, active pairing state, alert state และ pending sync state ก่อนประกาศ recovery สำเร็จ

## Rollback

Rollback ต้องเริ่มจากหยุดการ deploy ใหม่และระบุ version ที่ทราบว่าปลอดภัย จากนั้นหยุด ingestion อย่างปลอดภัย, export audit evidence, ป้องกันการส่ง Bundle ซ้ำด้วย idempotency key, restore application/database ตาม runbook และตรวจ health/readiness ก่อนเปิดรับข้อมูลอีกครั้ง

## Maintenance windows

การเปลี่ยน threshold, schema, migration, certificate, token scope, FHIR mapping หรือ checkpoint policy ต้องมี change ID, owner, risk review, pre-deploy tests, backup, rollback version และ post-deploy verification การเปลี่ยนแปลงที่กระทบ clinical signal ต้องผ่าน clinical governance review ก่อน


## Device Trust and ward workflow operations

ก่อน pilot ให้ตั้งค่า Admission Gateway/HIS integration ให้ Hub Core รับเฉพาะ opaque `patient_token` หรือ `encounter_token` ห้ามตั้งค่า barcode scanner ให้ส่ง raw HN/AN เข้า Hub API โดยตรง

ให้เริ่ม Device Trust ด้วย `SW_DEVICE_TRUST_MODE=observe` ระหว่างตรวจสอบพฤติกรรม C60/BLE Gateway จริง ในโหมดนี้ telemetry ที่ยังยืนยันไม่ได้จะถูก audit และอาจเดินต่อเพื่อ shadow evaluation แต่ห้ามถือเป็นหลักฐานที่ผ่าน cryptographic trust ให้เปลี่ยนเป็น `enforce` เมื่อผ่านการลงทะเบียน public key, proxy identity, clock behavior, key custody และ rollback procedure แล้ว

สำหรับ output interaction ให้ resolve NFC pointer, ตรวจ session state, ขอ `RESET_PENDING` และต้องมี operator ยืนยัน `RESET` อย่างชัดเจน หากมี unresolved incident ต้องทำ incident freeze ก่อน reset หรือ discharge ใช้ hot-swap เฉพาะผู้ป่วย/encounter เดิมและต้องสร้าง opaque `handover_id` ใหม่ ส่วน discharge ใช้เมื่อ encounter สิ้นสุด

Routine Session Close จะสร้าง summary digest และ clear volatile application buffer หลัง state transition commit สำเร็จ ส่วน Incident-Triggered Freeze จะเก็บ recent forensic window และต้องแยกจาก routine digest เสมอ local anchor เป็นเพียง tamper-evident evidence ภายใน Edge trust boundary ห้ามเรียกว่า external WORM หรือ tamper-proof

ดูรายละเอียด endpoint scopes, state transitions, retention language และ external validation gates ได้ที่ `WARD_WORKFLOW_CONTRACT.md`


## Tablet-only auto-run and state restore

The Tablet-only appliance should boot directly into the local Hub service and kiosk UI without a keyboard or per-bed configuration. Use the templates under `deploy/tablet/` as a starting point for the service supervisor and kiosk shell; adapt the user, display session, storage paths and OS policy to the selected tablet.

On startup the Edge service must restore SQLite/WAL state, Device Trust credentials, sessions, alerts, forensic records, idempotency state and the bounded telemetry checkpoint before the UI declares itself restored. The kiosk screen should show `RESTORED`, last state time, last telemetry freshness, trust state, offline state and `RECONCILIATION REQUIRED` whenever a session has no fresh heartbeat, has a pending reset/incident, or has a credential/state problem.

A restored pairing is not proof that the same patient or wristband is physically present. Operators must reconcile stale sessions using the state-aware reset, hot-swap or discharge workflow. The system must not automatically confirm reset, clear unresolved incidents, reassign patient tokens or promote stale telemetry to a fresh green state.

The local UI endpoint is restricted to the tablet loopback path in the reference design. Do not expose the kiosk bootstrap endpoint to the ward network without adding an authenticated UI gateway and a separate maintenance boundary.


## Roaming Tablet walk-round operations

A Roaming Tablet is an authenticated operational client, not the ward source of truth. At the start of a walk-round, the operator must confirm the ward name, `source=fixed-edge-hub`, snapshot cursor/revision, connection state and freshness age. The Tablet must display `OFFLINE — LAST KNOWN STATE` whenever it cannot reach the Fixed Hub.

The Tablet may acknowledge an alert or acknowledge an admission task through the authenticated roaming command API when the Hub is reachable. Every command uses a command ID, idempotency key and expected revision. A `409 STALE_REVISION` result means the Tablet must refresh the snapshot and not retry the old mutation blindly.

In the initial pilot, the Tablet must not confirm RESET, discharge, hot-swap, pairing changes, credential changes, incident freeze or purge while disconnected. `RESET_REQUEST` may enter `RESET_PENDING` when the Fixed Hub validates the state, but `RESET_CONFIRM` remains a live Fixed Hub action. If a command is rejected, display `REQUIRES RECONCILIATION` and use the documented manual fallback rather than silently retrying forever.

The BMAX Tablet must remain managed, locked to the approved kiosk/application profile, protected against screenshots and clipboard leakage where feasible, and revoked when lost. The current software baseline verifies scope, revision and idempotency; it does not by itself prove managed-device attestation, Android encrypted cache or real ward Wi-Fi performance.
