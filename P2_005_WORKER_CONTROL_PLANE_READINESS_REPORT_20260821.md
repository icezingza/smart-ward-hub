# P2-005 Worker Control-Plane Readiness Report

**วันที่:** 21 สิงหาคม 2026 (GMT+7)
**Task ID:** `P2-005-WCP-001`
**สถานะ:** `Applied` → software phase-end verification ผ่าน; external/persistent deployment ยังไม่เริ่ม
**Owner role:** Reliability operator + control-room coordinator

## 1. ขอบเขต

รอบนี้สร้าง worker control-plane แบบ deterministic และ in-process สำหรับงาน non-clinical ที่ allowlist ไว้เพียง `BACKUP_REPORT` และ `EVIDENCE_REPORT` โดยไม่มี scheduler, background thread, network client, subprocess, broker, persistent queue หรือ external side effect

ส่วนประกอบนี้เป็น control contract ไม่ใช่การเปิดใช้งาน worker mesh ใน production และไม่ใช่คำสั่งให้รันงานอัตโนมัติบน Acer หรือใน ward

## 2. Controls ที่ implement

| Control | Evidence/behavior | สถานะ |
|---|---|---|
| Job allowlist | จำกัด job type และ handler ที่ระบุไว้ล่วงหน้า | Implemented |
| Approval separation | requester และ approver ต้องเป็น role ที่ allowlist และต้องต่างกัน | Implemented |
| Non-clinical boundary | ปฏิเสธ `external_side_effects_allowed` และ `clinical_state_mutation` | Implemented |
| Idempotency | replay ด้วย key เดิมและ fingerprint เดิมคืน job เดิม; fingerprint mismatch ปฏิเสธ | Implemented |
| Duplicate job identity | `job_id` ซ้ำกับ payload ใหม่ถูกปฏิเสธ | Implemented |
| Bounded attempts | จำกัด `max_attempts` ไม่เกิน 3 | Implemented |
| Lease control | claim ได้ครั้งเดียว มี bounded lease expiry และ worker identity | Implemented |
| Stale lease stop | lease หมดอายุแล้วเปลี่ยนเป็น `BLOCKED` และต้อง reconcile | Implemented |
| Recovery separation | recovery actor ต้องเป็น role ที่อนุมัติและห้ามชนกับ original approver | Implemented |
| Fail-closed failure | retryable failure กลับ `QUEUED` ตามขอบเขต; terminal/unexpected failure เป็น `FAILED` โดยไม่เปิดเผย exception | Implemented |
| Audit integrity | append-only in-memory audit events ต่อ hash chain และตรวจ chain ได้ | Implemented |
| Mutation isolation | copy args/result/audit snapshot เพื่อไม่ให้ caller แก้ internal state | Implemented |

## 3. Verification evidence

Focused และ adversarial tests ผ่าน:

| Test | ผล |
|---|---|
| `test_worker_control_plane.py` | PASS |
| Idempotency/PII/role/side-effect boundary | PASS |
| Concurrent duplicate claim serialization | PASS |
| Bounded retry และ terminal failure | PASS |
| Stale lease stop/reconciliation | PASS |
| Recovery approver separation-of-duties | PASS |
| Audit-chain tamper detection | PASS |
| `test_p2_005_worker_phase_end_hardening.py` | PASS |
| Static no-scheduler/network/subprocess side-effect check | PASS |
| Private-key block scan | PASS |
| `git diff --check` | PASS |

## 4. State model

สถานะที่ใช้ใน control contract คือ `QUEUED → RUNNING → SUCCEEDED`, `QUEUED → RUNNING → FAILED`, หรือ `RUNNING → BLOCKED → QUEUED/FAILED` หลัง stale-lease reconciliation เท่านั้น การ requeue หลัง stale lease ไม่เกิดขึ้นเองและต้องมี reconciliation reference จาก recovery role

## 5. Rollback และ stop conditions

Rollback ทำได้โดย revert commit ของ `worker_control_plane.py`, `test_worker_control_plane.py`, `test_p2_005_worker_phase_end_hardening.py`, `run_all_tests.py`, รายงานนี้ และ backlog notes จากนั้นต้อง rerun focused tests, master regression และ release-freeze alignment

ต้องหยุดทันทีหากมี requirement ให้ worker ส่งข้อมูลออกนอก trust boundary, แก้ clinical state, เปลี่ยน authorization flags, รัน subprocess, ใช้ raw patient identity, สร้าง persistent scheduler หรือทำ autonomous retry ต่อ external API โดยไม่มี owner, approval, custody และ rollback contract แยกต่างหาก

## 6. Claim boundary

ผลลัพธ์นี้จัดเป็น **software-preparation evidence** และ **functional verification passed** สำหรับ in-process worker control contract เท่านั้น ยังไม่ใช่หลักฐานของ multi-process queue, distributed lock, crash recovery, durable job store, external API delivery, OS service supervision, production scheduling, clinical workflow หรือ external authorization

สถานะโครงการยังคงเป็น **controlled production prototype**, **P0-hardened software baseline**, **pilot-ready foundation** และ **clinical validation pending**. ห้ามเรียกงานนี้ว่า production-ready, clinical-ready หรือ autonomous clinical worker mesh

## 7. Evidence paths

- `worker_control_plane.py`
- `test_worker_control_plane.py`
- `test_p2_005_worker_phase_end_hardening.py`
- `P2_005_WORKER_CONTROL_PLANE_READINESS_REPORT_20260821.md`
- `tasks.md`
- `run_all_tests.py`
