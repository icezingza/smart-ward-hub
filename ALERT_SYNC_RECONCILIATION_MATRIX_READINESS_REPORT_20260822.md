# Alert/Sync Reconciliation Matrix Readiness Report

**วันที่:** 22 สิงหาคม 2026

**สถานะ:** `SOFTWARE_VERIFIED` / `SIMULATION_ONLY`

**Product boundary:** `CONTROLLED_PRODUCTION_PROTOTYPE`

**Pilot boundary:** `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`

## สรุปผล

Smart Ward Hub มี reconciliation contract แบบ pure/read-only สำหรับตรวจ alert lifecycle, sync retry/dead-letter, stale revision ของ roaming command และ unresolved incident ที่ขาด forensic package แล้ว โดย evaluator ใช้ precedence แบบ fail-closed และทุกผลลัพธ์มี `resume_permitted`, `recovery_decision` และ `remediation_code` อย่างชัดเจน

การทดสอบยืนยันว่า acknowledged alert สามารถทำให้ **software monitoring resume eligibility** เป็นจริงได้ ขณะที่ unresolved alert ยังคงบล็อก reset/discharge แม้จะ acknowledged แล้วก็ตาม นอกจากนี้ incident-frozen session ที่ไม่มี forensic package, sync ที่ retry limit เกิน, sync stale revision และ roaming command ที่ expected revision ไม่ตรงกับ authoritative revision จะไม่ถูกอนุญาตให้ resume

> ผลนี้เป็น **functional verification passed** ใน software simulation เท่านั้น ไม่ใช่หลักฐานจาก ward จริง ไม่ใช่ clinical validation และไม่เปลี่ยนสถานะ authorization ใด ๆ

## Scope และ contract

| Area | Covered behavior | Expected result |
|---|---|---|
| Alert acknowledgement | Acknowledged แต่ยังไม่ resolved | Monitoring resume eligibility ได้; reset/discharge ยังถูกบล็อก |
| Unresolved alert | Alert ยังเปิดอยู่ | `UNRESOLVED_ALERT_BLOCKS_RESET` และ `resume_permitted=false` สำหรับ destructive operation |
| Incident freeze | Session เป็น `INCIDENT_FROZEN` และไม่มี forensic package | `FORENSIC_PACKAGE_REQUIRED` / fail-closed |
| Sync success | Structured 200 acknowledgment | `SYNC_ACKNOWLEDGED` |
| Sync retry | Retry ยังไม่เกิน bounded limit | `SYNC_RETRY_PENDING` / operator confirmation required |
| Sync dead-letter | Retry limit exceeded หรือถูก mark dead-letter | `SYNC_DEAD_LETTER` / reconciliation required |
| Sync stale revision | Conflict ไม่ใช่ transport failure | `STALE_REVISION_409`; ห้าม retry แบบ blind |
| Roaming command | `expected_revision != current_revision` | Reject แบบ 409-style stale revision |
| Authorization mutation | มี production/clinical/runtime/external authority เข้ามาใน observation | `AUTHORIZATION_BOUNDARY_LOCKED`; resume false |

## Decision contract

ทุก decision row มีฟิลด์บังคับต่อไปนี้:

```text
scenario_id
operation
resume_permitted
recovery_decision
remediation_code
reason
opaque_refs
authorization_boundary_locked
```

ค่าที่ใช้ใน `recovery_decision` มีเพียง `RECONCILIATION_REQUIRED`, `OPERATOR_CONFIRMATION_REQUIRED` และ `SOFTWARE_RESUME_ELIGIBLE` โดย `SOFTWARE_RESUME_ELIGIBLE` เป็นเพียงผลการประเมินความพร้อมของ software rehearsal ไม่ใช่คำสั่ง resume และไม่ใช่ production authorization

## Evidence และการป้องกันข้อมูล

`alert_sync_reconciliation_matrix.py` ไม่มี database, network, scheduler, provider หรือ runtime mutation ใด ๆ และรับเฉพาะ observation ที่ผ่าน bounded/opaque-reference validation. `alert_ref`, `session_ref`, `bundle_ref` และ `command_ref` จะไม่ถูกส่งออกแบบ raw แต่ถูกแปลงเป็น deterministic opaque digest ใน decision/evidence output

`export_alert_sync_reconciliation.py` สร้าง machine-readable evidence แบบ read-only พร้อม hash-chained transcript. Exporter ตรวจ transcript integrity, source revision, authorization boundary และ redaction markers. ไม่สร้าง external receipt, ไม่ส่งข้อมูลออกนอกเครื่อง และไม่ทำการ resume จริง

## Verification record

| Gate | Result | Evidence |
|---|---|---|
| Focused/adversarial tests | PASS | `test_alert_sync_reconciliation_matrix.py` |
| AST no network/provider/scheduler imports | PASS | `test_alert_sync_reconciliation_matrix_phase_end_hardening.py` |
| Alert/reset/incident fail-closed rules | PASS | Focused test suite + matrix payload |
| Sync retry/dead-letter/stale revision | PASS | Focused test suite + matrix payload |
| Roaming stale revision | PASS | Focused test suite + matrix payload |
| Opaque reference/redaction scan | PASS | Focused suite + phase-end gate |
| No-self-authorization boundary | PASS | Phase-end gate |
| Hash-chained transcript | PASS | Exporter + phase-end gate |
| Private-key scan | PASS | Phase-end gate |
| `git diff --check` | PASS | Phase-end gate |

## Claim boundary

ผลลัพธ์นี้รองรับถ้อยคำ **controlled production prototype**, **functional verification passed**, **pilot-ready foundation** และ **clinical validation pending** เท่านั้น ไม่ควรใช้คำว่า clinical-ready, tamper-proof, HIPAA/PDPA compliant 100% หรือ production-ready จากผลนี้

ยังไม่ได้ยืนยันสิ่งต่อไปนี้:

1. Alert handling กับพยาบาลหรือ clinical escalation ใน ward จริง
2. HIS/EMR/FHIR acknowledgement และ reconciliation ผ่านระบบโรงพยาบาลจริง
3. Network outage, queue persistence และ durable dead-letter worker บน host จริง
4. Roaming Tablet ใน BMAX และ Fixed Hub authority arbitration บนอุปกรณ์จริง
5. Forensic package retention, external append-only anchoring และ trusted timestamp
6. Clinical review ของ reset/discharge safety และ alarm-fatigue workflow
7. External authorization หรือ independent reviewer decision

## สถานะ authorization ที่ต้องคงเดิม

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

- `alert_sync_reconciliation_matrix.py`
- `test_alert_sync_reconciliation_matrix.py`
- `test_alert_sync_reconciliation_matrix_phase_end_hardening.py`
- `export_alert_sync_reconciliation.py`
- `WARD_WORKFLOW_CONTRACT.md`
- `main.py` — roaming `409 STALE_REVISION`, `INCIDENT_FREEZE_REQUIRED` และ `ALERT_NOT_ACTIONABLE` contracts
- `models.py` — `Alert`, `SyncAttempt`, `RoamingCommand`, `ForensicPackage`, `WardSession`

## ข้อเสนอถัดไปภายใน

ลำดับถัดไปควรเป็น **operational sync/alert replay harness** ที่ใช้ fixture-only SQLite target เพื่อจำลอง duplicate acknowledgment, partial sync write, dead-letter replay และ stale snapshot refresh โดยต้องแยกจาก real HIS/EMR และต้องไม่เปิด runtime authority. หลังจากนั้นจึงค่อยเตรียม BMAX roaming UI contract และ Windows service recovery evidence ตาม dependency ของ P0/P2.
