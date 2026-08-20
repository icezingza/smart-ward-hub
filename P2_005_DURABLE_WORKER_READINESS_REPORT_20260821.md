# P2-005 Durable Worker Store Readiness Report

**วันที่:** 21 สิงหาคม 2026 (GMT+7)
**Task ID:** `P2-005-DWS-001`
**สถานะ:** `Applied` → software phase-end verification ผ่าน; production durable mode ยังถูก block
**Owner role:** Reliability operator + control-room coordinator

## 1. ขอบเขต

รอบนี้ต่อยอดจาก in-process worker control plane ด้วย SQLite-backed durable worker store ในโหมด `software_fixture` เท่านั้น เพื่อพิสูจน์ transactional claim, idempotency, restart persistence, bounded retry, expiring lease, stale-lease reconciliation, SQLite WAL/FULL และ audit-chain integrity

โหมดนี้ไม่เปิด scheduler, network client, subprocess, broker, distributed lock, external delivery หรือ clinical mutation และไม่อ้างว่าเป็น production durable queue

## 2. Controls ที่ implement

| Control | Evidence/behavior | สถานะ |
|---|---|---|
| Explicit mode gate | mode อื่นนอกจาก `software_fixture` ถูกปฏิเสธ | Implemented |
| SQLite durability fixture | เปิด `WAL`, `synchronous=FULL`, foreign keys และ integrity check | Implemented |
| Transactional submit | job/idempotency uniqueness และ audit event อยู่ใน transaction | Implemented |
| Transactional claim | `BEGIN IMMEDIATE` serialize claim ข้าม store instances | Implemented |
| Restart persistence | close/reopen แล้ว job state และ audit ยังคงอยู่ | Implemented |
| Idempotency | key เดิมกับ fingerprint เดิม replay ได้; conflict ถูกปฏิเสธ | Implemented |
| Bounded retry | `max_attempts` จำกัดไม่เกิน 3 | Implemented |
| Lease expiry | expired completion เปลี่ยน job เป็น `BLOCKED` แบบ commit แล้วหยุด | Implemented |
| Recovery reconciliation | stale lease ต้องใช้ approved recovery role และ reference | Implemented |
| Fail-closed data boundary | PII/secret/clinical mutation/external side effect ถูกปฏิเสธ | Implemented |
| Audit integrity | SQLite audit chain ตรวจ hash/sequence/previous hash ได้ | Implemented |
| Production durable policy | encryption-at-rest, backup/custody/retention/external approval ยังไม่มี จึง block | Unverified/Blocked |

## 3. Verification evidence

| Test/gate | ผล |
|---|---|
| `test_durable_worker_store.py` | PASS |
| WAL/FULL/restart persistence | PASS |
| Transactional concurrent claim serialization | PASS |
| Idempotency/PII/clinical boundary rejection | PASS |
| Bounded retry and stale-lease reconciliation | PASS |
| Expired completion committed `BLOCKED` transition | PASS |
| Audit tamper detection | PASS |
| `test_p2_005_durable_worker_phase_end_hardening.py` | PASS |
| No network/subprocess/scheduler import | PASS |
| Production durable mode fail-closed | PASS |
| Private-key block scan | PASS |
| `git diff --check` | PASS |

## 4. Recovery semantics

สถานะหลักคือ `QUEUED → RUNNING → SUCCEEDED`, `QUEUED → RUNNING → FAILED` หรือ `RUNNING → BLOCKED → QUEUED/FAILED` หลัง expiry reconciliation เท่านั้น หาก worker พยายาม complete หลัง lease หมดอายุ ระบบจะ commit `BLOCKED` และไม่ยอมรับผลลัพธ์โดยอัตโนมัติ

การ reopen database เป็นหลักฐานของ SQLite fixture restart persistence เท่านั้น ไม่ใช่หลักฐานของ abrupt power cut, filesystem corruption, disk-full หรือ OS service recovery บน Acer

## 5. Rollback และ stop conditions

Rollback ทำได้โดย revert `durable_worker_store.py`, `test_durable_worker_store.py`, `test_p2_005_durable_worker_phase_end_hardening.py`, `run_all_tests.py`, report นี้ และ backlog notes จากนั้นต้อง rerun focused tests, master regression และ release-freeze alignment

ต้องหยุดทันทีหากมี requirement ให้เปิด production durable mode โดยไม่มี encryption-at-rest, backup manifest/restore test, owner/custodian, retention/RPO/RTO, access control, key custody, migration policy หรือ external authorization ที่ตรวจสอบได้

## 6. Claim boundary

ผลลัพธ์นี้เป็น **software durable-queue fixture evidence** และ **functional verification passed** เท่านั้น ไม่ใช่ production queue, distributed worker mesh, crash-consistent power-loss proof, encrypted durable storage, backup/restore approval, OS service supervision, external delivery หรือ clinical automation

P2-005 ยังคงเป็น **In Progress**. สถานะโครงการยังเป็น **controlled production prototype**, **P0-hardened software baseline**, **pilot-ready foundation** และ **clinical validation pending**

## 7. Evidence paths

- `durable_worker_store.py`
- `test_durable_worker_store.py`
- `test_p2_005_durable_worker_phase_end_hardening.py`
- `P2_005_DURABLE_WORKER_READINESS_REPORT_20260821.md`
- `P2_005_WORKER_CONTROL_PLANE_READINESS_REPORT_20260821.md`
- `tasks.md`
