# Cross-Package Evidence Binding Readiness Report

**วันที่:** 22 สิงหาคม 2026

**สถานะ:** `SOFTWARE_VERIFIED` / `INTERNAL_EVIDENCE_BINDING`

**Product status:** `NOT_PRODUCTION_READY`

**Pilot status:** `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`

## สรุปผล

เพิ่ม cross-package binding checker สำหรับผูก evidence package 4 ชั้น ได้แก่ worker recovery transcript, operator approval/read-back, durable worker replay evidence และ release-freeze manifest. Checker ทำงานแบบ read-only โดยตรวจ source revision, freeze-listed artifact hash, transcript integrity, approval transcript/queue binding, durable replay boundary และ locked authorization boundary

Decision มีสองแบบ:

- `BOUND`: packages ทั้งหมดสอดคล้องกันในระดับ software evidence และ freeze manifest
- `RECONCILIATION_REQUIRED`: พบ mismatch อย่างน้อยหนึ่งรายการ ห้ามตีความเป็น approval หรือ resume eligibility

## Binding matrix

| Package | Binding ที่ตรวจ |
|---|---|
| Worker recovery transcript | schema, `transcript_integrity_valid`, correlation ref, source revision, freeze file hash |
| Operator approval/read-back | transcript ref/hash, queue backup ref/hash, source revision, actor/confirmation validation status |
| Durable worker replay | software fixture mode, no external transmission, no clinical mutation, no runtime replay, locked authority |
| Release freeze | freeze-listed artifact paths/hashes, `source_revision`, authorization boundary, origin relationship |

## Mismatch codes

| Code | ความหมาย | Stop rule |
|---|---|---|
| `FREEZE_ARTIFACT_NOT_LISTED` | evidence ไม่อยู่ใน freeze manifest | ห้ามใช้ evidence เป็น frozen package |
| `FREEZE_ARTIFACT_HASH_MISMATCH` | bytes ปัจจุบันไม่ตรง manifest | regenerate freeze ก่อนใช้ |
| `APPROVAL_TRANSCRIPT_HASH_MISMATCH` | approval ไม่ผูก transcript ปัจจุบัน | invalidate approval/read-back |
| `APPROVAL_QUEUE_REF_MISMATCH` | backup reference ต่างกัน | reconcile queue binding |
| `APPROVAL_QUEUE_HASH_MISMATCH` | queue binding digest ต่างกัน | regenerate approval |
| `DURABLE_REPLAY_BOUNDARY_MISMATCH` | replay/runtime boundary ถูกเปลี่ยน | fail closed และหยุด workflow |
| `SOURCE_REVISION_NOT_ANCESTOR_OF_FREEZE` | evidence revision lineage ไม่สอดคล้อง | refresh evidence/freeze |

## Verification behavior

Checker คำนวณ SHA-256 ของ artifact bytes ใน repository แล้วเทียบกับรายการ `files[].sha256` ของ freeze manifest. จากนั้นคำนวณ canonical hash ของ transcript events และ queue-binding details เพื่อเทียบกับ approval record. Durable evidence ต้องระบุ `SOFTWARE_FIXTURE`, `runtime_replay_executed=false`, `clinical_state_mutation_performed=false`, `external_transmission_performed=false` และ locked authority

ทุก mismatch คืน `RECONCILIATION_REQUIRED`; checker ไม่แก้ไฟล์ ไม่เขียนฐานข้อมูล ไม่ส่งข้อมูล และไม่เลื่อน authorization

## Verification record

| Gate | Result | Evidence |
|---|---|---|
| Synthetic bound fixture | PASS | `test_cross_package_evidence_binding.py` |
| Transcript hash mismatch | PASS | Adversarial mismatch test |
| Queue reference mismatch | PASS | Adversarial mismatch test |
| Durable boundary mutation | PASS | Adversarial mismatch test |
| Freeze artifact hash mismatch | PASS | Adversarial mismatch test |
| Repository-wide binding | Pending until evidence regeneration/freeze refresh | Checker |
| No network/provider/scheduler side effect | PASS | Phase-end AST scan |
| Redaction/private-key scan | PASS | Phase-end gate |
| No-self-authorization | PASS | Phase-end gate |
| Exporter round-trip | Pending until evidence regeneration | Phase-end gate |
| `git diff --check` | PASS | Phase-end gate |
| Master regression | Pending until commit/evidence/freeze sequence | `run_all_tests.py` |

## Claim boundary

ผลรองรับเฉพาะคำว่า **controlled production prototype**, **functional verification passed**, **pilot-ready foundation** และ **clinical validation pending**. Cross-package `BOUND` หมายถึง internal software artifacts สอดคล้องกันเท่านั้น ไม่ใช่ production readiness หรือ external authorization

ยังไม่ยืนยัน:

1. Independent reviewer acceptance หรือ external authority decision
2. Human operator sign-off ในระบบจริง
3. External signature, trusted timestamp, WORM custody หรือ HIS/EMR submission
4. Clinical validation, real ward execution หรือ hardware/service recovery
5. Production deployment, distributed queue และ external replay

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

- `cross_package_evidence_binding.py`
- `test_cross_package_evidence_binding.py`
- `test_cross_package_evidence_binding_phase_end_hardening.py`
- `export_cross_package_evidence_binding.py`
- `export_durable_worker_replay.py`
- `CROSS_PACKAGE_EVIDENCE_BINDING_READINESS_REPORT_20260822.md`

## งานถัดไปภายใน

หลัง checker เป็น `BOUND` และ freeze refresh ผ่าน ควรเพิ่ม consolidated internal handoff index ที่อ้างเฉพาะ binding snapshot นี้ โดยห้ามใช้เป็น external submission หรือ authorization record จนกว่าจะมี independent reviewer appointment และ external decision จริง
