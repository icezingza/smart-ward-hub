# Durable Worker Replay Contract Readiness Report

**วันที่:** 22 สิงหาคม 2026

**สถานะ:** `SOFTWARE_VERIFIED` / `SOFTWARE_FIXTURE`

**Product status:** `NOT_PRODUCTION_READY`

**Pilot status:** `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`

## สรุปผล

Smart Ward Hub มี orchestration contract สำหรับ durable worker replay บน SQLite `software_fixture` target แล้ว โดยเชื่อม state ของ `DurableWorkerStore`, lease expiry, restart reconciliation, retry-limit/dead-letter classification และ `worker_queue_backup` isolated restore เข้าด้วยกัน

การทดสอบยืนยันว่า lease ที่หมดอายุจะถูกเปลี่ยนเป็น `BLOCKED` และต้องผ่าน reconciliation ก่อน requeue; retry limit ที่หมดจะถูกจัดเป็น `RETRY_LIMIT_EXCEEDED_DEAD_LETTER`; dead-letter replay ต้องมี operator confirmation ก่อนให้ software replay eligibility; และ queue backup/restore ยังคงผูก schema, database hash, source revision และ authorization boundary

> ผลนี้เป็น **functional verification passed** ใน SQLite fixture-only simulation เท่านั้น ไม่ใช่หลักฐานของ distributed worker production, external queue, clinical action หรือ real disaster recovery

## Decision flow

| Stage | Result | Execution |
|---|---|---|
| Running lease expires | `LEASE_EXPIRED_REQUIRES_RECONCILIATION` | Worker ถูก block |
| Recovery reconciliation | `REQUEUE` หรือ `FAIL` ตาม allowlist | ต้องใช้ approved recovery role |
| Retryable failure | `QUEUED` จนถึง bounded attempt limit | ไม่มี external delivery |
| Retry limit exhausted | `RETRY_LIMIT_EXCEEDED_DEAD_LETTER` | ไม่ replay อัตโนมัติ |
| Dead-letter without confirmation | `OPERATOR_CONFIRMATION_REQUIRED` | `replay_permitted=false` |
| Dead-letter with confirmation | `SOFTWARE_REPLAY_ELIGIBLE` | `replay_executed=false` |
| Isolated queue backup restore | `SOFTWARE_RESTORE_VERIFIED` | แยก target และ non-production |

## การตรวจสอบที่ทำจริง

### Lease expiry และ restart reconciliation

Harness เปิด durable worker store ใน SQLite WAL/FULL fixture, submit job, claim job ด้วย lease, จำลอง process boundary ด้วยการเปิด store ใหม่หลัง lease expiry, ย้าย job เป็น `BLOCKED`, ตรวจ classification, แล้ว requeue ผ่าน approved recovery role. หลัง recovery ตรวจ `integrity_check=ok`, `journal_mode=wal`, `synchronous=2` และ `audit_chain_valid=true`

### Dead-letter replay

Harness ทำ retryable failure จนครบ bounded `max_attempts=3` จนสถานะเป็น `FAILED` พร้อม `RETRY_LIMIT_EXCEEDED`. ขั้นแรกคืน `OPERATOR_CONFIRMATION_REQUIRED`; ขั้นที่มี confirmation คืน `SOFTWARE_REPLAY_ELIGIBLE` แต่ไม่ claim, ไม่ execute และไม่เปลี่ยน production/runtime authority

### Queue backup/restore

Harness ใช้ `create_worker_queue_backup` และ `restore_worker_queue_backup` ไปยัง isolated temporary target โดยตรวจ worker queue schema, database hash, binding hash, source revision, `software_fixture` mode, `external_authority=false`, `clinical_state_allowed=false`, SQLite integrity และ audit chain หลัง restore. Target จริงและ encrypted custody ยังไม่ได้ถูกทดสอบ

## Verification record

| Gate | Result | Evidence |
|---|---|---|
| Focused/adversarial tests | PASS | `test_durable_worker_replay_contract.py` |
| Lease expiry/restart reconciliation | PASS | `durable_worker_replay_contract.py` rehearsal |
| Dead-letter classification/replay gate | PASS | Rehearsal + focused tests |
| Queue backup/restore binding | PASS | Rehearsal + existing `worker_queue_backup.py` contract |
| SQLite WAL/FULL/integrity | PASS | Rehearsal health output |
| Audit-chain continuity | PASS | Rehearsal health output |
| No network/provider/scheduler side effect | PASS | Phase-end gate |
| No-self-authorization | PASS | Phase-end gate |
| Redaction/private-key scan | PASS | Phase-end gate |
| `git diff --check` | PASS | Phase-end gate |
| Master regression | Pending until commit/freeze refresh | `run_all_tests.py` |

## Claim boundary

ผลรองรับเฉพาะคำว่า **controlled production prototype**, **functional verification passed**, **pilot-ready foundation** และ **clinical validation pending**. ไม่ควรใช้คำว่า clinical-ready, tamper-proof, HIPAA/PDPA compliant 100% หรือ production-ready

ยังไม่ยืนยัน:

1. Distributed lock, multi-host worker, scheduler และ service supervisor บน production host
2. Encrypted backup destination, retention, RPO/RTO และ custody จริง
3. External queue/dead-letter broker และ replay endpoint
4. Network outage, OIDC/mTLS, response authenticity และ provider delivery
5. Clinical state mutation หรือ real ward escalation
6. Windows service recovery และ Acer hardware power-loss behavior
7. Independent reviewer decision หรือ external authorization

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

- `durable_worker_replay_contract.py`
- `test_durable_worker_replay_contract.py`
- `test_durable_worker_replay_contract_phase_end_hardening.py`
- `durable_worker_store.py`
- `worker_queue_backup.py`
- `backup_restore.py`
- `DURABLE_WORKER_REPLAY_CONTRACT_READINESS_REPORT_20260822.md`

## งานถัดไปภายใน

ควรใช้ผลนี้เป็นฐานสำหรับ **operator-facing worker recovery transcript** ที่แสดง lease owner, reconciliation ref, decision และ queue backup binding แบบ redacted โดยยังคงไม่เปิด replay execution. หลังจากนั้นจึงพิจารณา host/service recovery evidence บน Acer เมื่อมี physical bench และ external owner approval จริง
