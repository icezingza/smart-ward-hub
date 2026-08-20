# P2-005 Worker Queue Backup Readiness Report

**วันที่:** 21 สิงหาคม 2026 (GMT+7)
**Task ID:** `P2-005-WQB-001`
**สถานะ:** `Applied` → software backup/restore verification ผ่าน; production backup custody ยัง block
**Owner role:** Reliability operator + backup manager

## 1. ขอบเขต

รอบนี้เพิ่ม binding layer ระหว่าง durable worker SQLite fixture กับ P1-001 SQLite backup API โดยสร้าง `worker_queue_binding.json` ที่ผูก backup ID, source revision, worker-store schema version, database artifact SHA-256, software-fixture mode และ no-authorization flags

การ restore ใช้ separate target และตรวจ binding/database checksum ก่อนยอมรับผลลัพธ์ ระบบยังไม่อ้าง encryption-at-rest, external custody, retention, RPO/RTO หรือ production backup approval

## 2. Controls ที่ implement

| Control | Evidence/behavior | สถานะ |
|---|---|---|
| Store schema binding | ต้องเป็น `p2-005-durable-worker-v1` | Implemented |
| Backup binding schema | ต้องเป็น `smart-ward-worker-queue-backup-v1` | Implemented |
| Database artifact binding | binding hash ต้องตรงกับ manifest database SHA-256 และไฟล์จริง | Implemented |
| Source revision binding | source revision ต้องมีค่าและถูกเก็บใน binding | Implemented |
| Authorization boundary | `external_authority=false`, `clinical_state_allowed=false` | Implemented |
| Separate-target restore | target database ต้องอยู่นอก bundle และ restore ผ่าน temp target | Implemented |
| Exact confirmation | ต้องใช้ `I_UNDERSTAND_RESTORE_TO_NONPRODUCTION_TARGET` | Implemented |
| Tamper rejection | binding hash, database hash, manifest/checksum mismatch ถูกปฏิเสธ | Implemented |
| Secret boundary | ใช้ inherited backup artifact safety checks; ไม่รวม private keys/secrets | Implemented |
| Physical storage claim | ผลลัพธ์คง `physical_storage_validation=UNVERIFIED` | Implemented |

## 3. Verification evidence

| Test/gate | ผล |
|---|---|
| `test_worker_queue_backup.py` | PASS |
| SQLite backup binding and separate-target restore | PASS |
| Confirmation rejection | PASS |
| Binding hash tamper rejection | PASS |
| Database artifact tamper rejection | PASS |
| `test_p2_005_worker_backup_phase_end_hardening.py` | PASS |
| No network/subprocess/scheduler import | PASS |
| No-authorization binding check | PASS |
| Private-key block scan | PASS |
| `git diff --check` | PASS |

## 4. Recovery and custody boundary

การ restore ที่ผ่านหมายถึง SQLite software restore verification เท่านั้น ไม่ใช่ physical power-loss recovery, filesystem corruption recovery, encrypted backup approval หรือ external custody verification การเปิด production durable worker mode ยังต้องมี encryption-at-rest, backup destination owner, custodian, retention, RPO/RTO, access control, key ceremony, restore drill และ external approval

## 5. Rollback และ stop conditions

Rollback ทำได้โดย revert `worker_queue_backup.py`, `test_worker_queue_backup.py`, `test_p2_005_worker_backup_phase_end_hardening.py`, `run_all_tests.py`, report นี้ และ backlog notes จากนั้นต้อง rerun P1-001 backup regression, P2-005 durable worker tests, master regression และ release-freeze alignment

ต้องหยุดทันทีหากมีการนำ bundle ไปใช้กับ production database, ใช้ real patient data, ยืนยัน encryption/custody จาก local hash เพียงอย่างเดียว, restore ทับ source/bundle, หรือเปลี่ยน `external_authority`/clinical flags เป็น true โดยไม่มี external decision

## 6. Claim boundary

ผลลัพธ์นี้เป็น **software backup/restore contract verification** และ **functional verification passed** เท่านั้น ไม่ใช่ production backup readiness, external custody, WORM storage, encrypted-at-rest certification, clinical validation หรือ production authorization

P2-005 ยังคงเป็น **In Progress**. สถานะโครงการยังเป็น **controlled production prototype**, **P0-hardened software baseline**, **pilot-ready foundation** และ **clinical validation pending**

## 7. Evidence paths

- `worker_queue_backup.py`
- `test_worker_queue_backup.py`
- `test_p2_005_worker_backup_phase_end_hardening.py`
- `backup_restore.py`
- `test_backup_restore.py`
- `P2_005_WORKER_QUEUE_BACKUP_READINESS_REPORT_20260821.md`
- `tasks.md`
