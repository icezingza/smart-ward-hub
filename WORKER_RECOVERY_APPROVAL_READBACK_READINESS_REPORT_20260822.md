# Worker Recovery Approval / Read-back Readiness Report

**วันที่:** 22 สิงหาคม 2026

**สถานะ:** `SOFTWARE_VERIFIED` / `LOCAL_SOFTWARE_SIMULATION`

**Product status:** `NOT_PRODUCTION_READY`

**Pilot status:** `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`

## สรุปผล

Smart Ward Hub มี Operator Approval / Read-back Contract สำหรับ worker recovery transcript แล้ว โดย contract บังคับ actor separation ระหว่าง requester, approver และ read-back verifier, explicit confirmation, timezone-aware timestamps, transcript SHA-256 binding, queue-backup binding และ software-only execution scope

Approval ที่ผ่านการตรวจจะคืน `APPROVED_FOR_SOFTWARE_REHEARSAL` ได้เฉพาะในขอบเขต evidence/read-back ของ local software rehearsal. Approval นี้ไม่เปิด replay execution, ไม่อนุญาต production, ไม่สร้าง external authority และไม่เปลี่ยน clinical validation boundary

> ผลนี้เป็น **functional verification passed** ใน local software simulation เท่านั้น ไม่ใช่ human sign-off จริง, independent reviewer decision หรือ production authorization

## Contract ที่ตรวจ

| Control | Required behavior | Result |
|---|---|---|
| Actor separation | requester, approver และ read-back role ต้องแตกต่างกัน | PASS |
| Explicit confirmation | ใช้ confirmation code ที่กำหนดตรงตัวทั้ง approval และ read-back | PASS |
| Timestamp | approval ต้องมาก่อนหรือเท่ากับ read-back และต้อง timezone-aware | PASS |
| Transcript binding | `transcript_sha256` ต้องตรงกับ redacted transcript | PASS |
| Queue binding | `queue_backup_ref` และ binding hash ต้องตรงกับ `QUEUE_BACKUP_BINDING_VERIFIED` event | PASS |
| Scope | `SOFTWARE_REHEARSAL_ONLY` เท่านั้น | PASS |
| Execution lock | `replay_execution_requested=false`, `replay_executed=false` | PASS |
| Authorization lock | external/clinical/production/runtime authority คง locked | PASS |
| Schema | unknown fields และ missing fields ถูกปฏิเสธ | PASS |

## Decision lifecycle

```text
READBACK_REQUIRED
  -> APPROVED_FOR_SOFTWARE_REHEARSAL
  -> no replay execution
  -> no production/runtime authorization
```

Boundary mutations, actor collision, wrong confirmation, out-of-order timestamp, transcript tamper, queue reference/hash tamper และ execution request จะถูกปฏิเสธแบบ fail-closed

## Evidence integrity

`worker_recovery_approval.py` ตรวจ exact schema, opaque typed references, SHA-256 bindings, transcript integrity, queue binding event, role allowlist, role separation, confirmation, timestamp ordering และ locked authorization boundary

`export_worker_recovery_approval.py` สร้าง machine-readable read-back evidence แบบ redacted พร้อม source revision, validation result, claim boundary และ redaction flag. Exporter ไม่เรียก network/provider/scheduler และไม่ทำงาน replay

## Verification record

| Gate | Result | Evidence |
|---|---|---|
| Focused/adversarial tests | PASS — 7 cases | `test_worker_recovery_approval.py` |
| Actor separation | PASS | Approval validator + adversarial test |
| Transcript binding tamper | PASS | Adversarial test |
| Queue binding tamper | PASS | Adversarial test |
| Confirmation/timestamp boundary | PASS | Adversarial test |
| Authorization/execution mutation | PASS | Adversarial test |
| Exact schema/unknown fields | PASS | Adversarial test |
| No network/provider/scheduler side effect | PASS | Phase-end AST scan |
| Exporter round-trip | PASS | Phase-end gate |
| Redaction/private-key scan | PASS | Phase-end gate |
| No-self-authorization | PASS | Phase-end gate |
| `git diff --check` | PASS | Phase-end gate |
| Master regression | Pending until commit/freeze refresh | `run_all_tests.py` |

## Claim boundary

ผลรองรับเฉพาะคำว่า **controlled production prototype**, **functional verification passed**, **pilot-ready foundation** และ **clinical validation pending**. ไม่ควรใช้คำว่า clinical-ready, tamper-proof, HIPAA/PDPA compliant 100% หรือ production-ready

ยังไม่ยืนยัน:

1. Human operator approval/signature หรือ independent reviewer read-back จริง
2. Production identity, access control และ approval service
3. External signature, certificate, trusted timestamp หรือ WORM custody
4. Production worker execution, queue lease หรือ host/service recovery
5. Clinical escalation, patient-safety action หรือ real ward workflow
6. External authorization decision

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

- `worker_recovery_approval.py`
- `test_worker_recovery_approval.py`
- `test_worker_recovery_approval_phase_end_hardening.py`
- `export_worker_recovery_approval.py`
- `worker_recovery_transcript.py`
- `WORKER_RECOVERY_APPROVAL_READBACK_READINESS_REPORT_20260822.md`

## งานถัดไปภายใน

ควรเพิ่ม approval/read-back evidence นี้เข้า consolidated internal handoff index และสร้าง cross-package binding check ระหว่าง transcript, approval, durable worker replay evidence และ release-freeze source revision โดยยังไม่ส่งออกนอก repository และไม่เปลี่ยน External Gate status
