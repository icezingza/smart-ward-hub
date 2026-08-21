# Worker Recovery Transcript Readiness Report

**วันที่:** 22 สิงหาคม 2026

**สถานะ:** `SOFTWARE_VERIFIED` / `LOCAL_SOFTWARE_SIMULATION`

**Product status:** `NOT_PRODUCTION_READY`

**Pilot status:** `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`

## สรุปผล

Smart Ward Hub มี operator-facing recovery transcript แบบ redacted สำหรับสรุป lease expiry, reconciliation reference, operator decision, dead-letter replay eligibility และ queue-backup binding แล้ว Transcript ถูกออกแบบเป็น evidence artifact แบบ read-only และ hash-chained โดยไม่ claim, execute หรือ authorize worker replay

Transcript lifecycle ที่ผ่านการตรวจคือ:

```text
LEASE_EXPIRY_OBSERVED
  -> LEASE_RECONCILIATION_RECORDED
  -> DEAD_LETTER_OBSERVED
  -> DEAD_LETTER_REPLAY_ELIGIBILITY_RECORDED
  -> QUEUE_BACKUP_BINDING_VERIFIED
```

ทุก event มี `event_seq`, `event_hash`, `previous_hash`, `operator_role`, `correlation_ref`, `decision`, `remediation_code` และ redacted details. Raw job ID, worker ID, reconciliation ref และ backup ID ถูกแทนด้วย opaque digest references

> ผลนี้เป็น **functional verification passed** ใน local software simulation เท่านั้น ไม่ใช่ operator evidence จาก production host, ward จริง หรือ independent review จริง

## Decision และ evidence matrix

| Event | Decision | Evidence captured | Execution |
|---|---|---|---|
| Lease expiry observed | `RECONCILIATION_REQUIRED` | opaque job/worker/reconciliation refs | ไม่ execute |
| Lease reconciliation recorded | `SOFTWARE_REPLAY_ELIGIBLE` | resulting queued state, role-bound confirmation | ไม่ claim worker |
| Dead-letter observed | `OPERATOR_CONFIRMATION_REQUIRED` | retry-limit classification | ไม่ replay |
| Dead-letter eligibility recorded | `SOFTWARE_REPLAY_ELIGIBLE` | replay permitted flag, runtime authority `NONE` | `replay_executed=false` |
| Queue backup binding verified | `SOFTWARE_REPLAY_ELIGIBLE` | backup/source refs, binding/audit verification | ไม่ส่งออกนอกเครื่อง |

## Redaction และ integrity

`worker_recovery_transcript.py` ตรวจ role allowlist, opaque references, bounded details, timezone-aware timestamps และ raw identity/secret markers. Transcript ใช้ SHA-256 hash chain ต่อ event; `verify()` ตรวจ sequence, previous hash, event hash และ marker scan

`export_worker_recovery_transcript.py` สร้าง machine-readable evidence พร้อม source revision, authorization boundary, claim boundary และ `redaction_verified`. Exporter ไม่มี network/provider/scheduler integration และไม่เปิด replay execution

## Verification record

| Gate | Result | Evidence |
|---|---|---|
| Focused/adversarial tests | PASS | `test_worker_recovery_transcript.py` |
| Lifecycle event coverage | PASS | Transcript builder + phase-end gate |
| Lease/reconciliation summary | PASS | Transcript event 1–2 |
| Dead-letter decision summary | PASS | Transcript event 3–4 |
| Queue-backup binding summary | PASS | Transcript event 5 |
| Hash-chain integrity | PASS | Transcript `verify()` |
| No network/provider/scheduler side effect | PASS | Phase-end AST scan |
| No-self-authorization | PASS | Phase-end gate |
| Redaction/private-key scan | PASS | Phase-end gate |
| Exporter round-trip | PASS | Phase-end gate |
| `git diff --check` | PASS | Phase-end gate |
| Master regression | Pending until commit/freeze refresh | `run_all_tests.py` |

## Claim boundary

ผลรองรับเฉพาะคำว่า **controlled production prototype**, **functional verification passed**, **pilot-ready foundation** และ **clinical validation pending**. ไม่ควรใช้คำว่า clinical-ready, tamper-proof, HIPAA/PDPA compliant 100% หรือ production-ready

ยังไม่ยืนยัน:

1. Human operator actually reviewed or signed the transcript
2. Production worker/service lease behavior on Acer or Windows host
3. Distributed queue, scheduler and multi-host lock evidence
4. Encrypted backup custody, retention, RPO/RTO and external restore evidence
5. Clinical escalation, nurse workflow or patient-safety action
6. Independent reviewer reproduction or external decision

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

- `worker_recovery_transcript.py`
- `test_worker_recovery_transcript.py`
- `test_worker_recovery_transcript_phase_end_hardening.py`
- `export_worker_recovery_transcript.py`
- `durable_worker_replay_contract.py`
- `worker_queue_backup.py`
- `WORKER_RECOVERY_TRANSCRIPT_READINESS_REPORT_20260822.md`

## งานถัดไปภายใน

ควรใช้ transcript นี้เป็นรูปแบบ evidence สำหรับ **operator approval/read-back contract** ที่ตรวจ actor separation, explicit confirmation, timestamp และ artifact binding แบบ software-only ก่อนเตรียม physical host/service recovery เมื่อมี external owner appointment จริง
