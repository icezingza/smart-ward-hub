# P0-004 Recovery Snapshot Integrity Hardening Report

**วันที่:** 21 สิงหาคม 2026 (GMT+7)
**Task ID:** `P0-004-SH-001`
**สถานะ:** `Applied` → รอ phase-end และ release-freeze verification
**Owner role:** Reliability operator + security auditor

## 1. ขอบเขตและเหตุผล

รอบนี้เพิ่มการตรวจสอบความถูกต้องของ checkpoint ที่ถูกอ่านกลับเข้า Edge Hub หลัง process restart โดยถือว่าไฟล์ checkpoint เป็น untrusted input ซึ่งอาจ stale, partial, corrupt หรือถูกแก้ไขนอก process ได้ งานนี้อยู่ภายใน software trust boundary และไม่เปิดใช้งานจริงกับ Acer, HIS, IdP, mTLS, external anchor หรือ clinical workflow

เป้าหมายคือให้การ restore เป็น **fail-closed** เมื่อพบข้อมูลที่ไม่สอดคล้องหรือมีข้อมูลต้องห้าม โดยไม่ทำให้ PII หรือ sequence state ที่อาจทำให้เกิด replay/rollback ถูกนำกลับเข้า in-memory telemetry buffer

## 2. การเปลี่ยนแปลงที่ทำจริง

| ไฟล์ | การเปลี่ยนแปลง | สถานะ |
|---|---|---|
| `edge_runtime.py` | เพิ่ม `_restored_samples_are_safe()` เพื่อตรวจ sample type, forbidden PII keys, sequence type และ monotonic ordering | Implemented |
| `edge_runtime.py` | ปฏิเสธ checkpoint ที่ `last_sequence` เป็น boolean/ค่าติดลบ/ชนิดผิด หรือไม่ตรงกับ sequence ล่าสุดของ sample | Implemented |
| `power_loss_recovery_harness.py` | เพิ่ม fault scenarios สำหรับ PII-bearing checkpoint, duplicate sequence และ `last_sequence` mismatch | Implemented |
| `test_power_loss_recovery_harness.py` | ผูก assertions กับ invariant hardening และ scenario coverage ใหม่ | Implemented |
| `P0_POWER_LOSS_SOFTWARE_EVIDENCE.json` | Regenerate machine-readable evidence จาก harness ล่าสุด | Implemented |
| `P0_PHASE_HANDOFF.md`, `P0_STATUS_REPORT.md`, `tasks.md` | อัปเดต traceability และแยก software evidence จาก physical evidence | Implemented |

## 3. หลักฐานการทดสอบ

การทดสอบ focused ผ่านทั้งหมด:

| Test | ผล |
|---|---|
| `test_edge_runtime.py` | PASS |
| `test_p0_recovery.py` | PASS |
| `test_power_loss_recovery_harness.py` | PASS |
| `power_loss_recovery_harness.py --output P0_POWER_LOSS_SOFTWARE_EVIDENCE.json` | PASS |
| `test_p0_hardening.py` ด้วย isolated venv PATH | PASS |
| `git diff --check` | PASS |

Machine-readable evidence ระบุ `all_passed=true` และ `checkpoint_invariant_hardening=SOFTWARE_VERIFIED` ใน `P0_POWER_LOSS_SOFTWARE_EVIDENCE.json` โดย scenarios ล่าสุดมี `committed_restart`, `stale_temp_does_not_replace`, `corrupt_json_fails_closed`, `unsupported_and_malformed_payloads`, `pii_checkpoint_rejected`, `sequence_inconsistency_rejected` และ `last_sequence_mismatch_rejected`

## 4. การประเมินความเสี่ยงและ rollback

ความเสี่ยงหลักคือ checkpoint เก่าที่ไม่มี `sequence` field อาจยังคง restore ได้ตาม compatibility contract หากไม่มี invariant ที่ตรวจได้ ส่วน checkpoint ที่มี sequence แต่ไม่สอดคล้องกันจะถูกปฏิเสธทั้ง device เพื่อรักษา fail-closed behavior และหลีกเลี่ยงการ restore state ที่ไม่สามารถยืนยันลำดับได้

Rollback ทำได้โดย revert commit ของ task นี้ ซึ่งจะคืน `edge_runtime.py`, harness, tests และ evidence/documentation กลับสู่ revision ก่อนหน้า การ rollback ต้อง rerun focused tests, master regression และ release-freeze alignment ก่อนยอมรับสถานะใด ๆ

## 5. Claim boundary

ผลลัพธ์นี้เป็น **software fault-injection evidence** และยืนยันได้เฉพาะ `SOFTWARE_VERIFIED` สำหรับ checkpoint invariants เท่านั้น ไม่ใช่หลักฐานของการตัดไฟจริง, disk-full, filesystem corruption บน Acer Spin N17H2, SSD/storage-controller behavior, UPS/battery recovery, Windows boot/service recovery หรือ production deployment

สถานะยังคงเป็น **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation** และ **clinical validation pending**. ห้ามเปลี่ยนเป็น `production-ready`, `clinical-ready`, `tamper-proof` หรือ `HIPAA/PDPA compliant 100%` จากงานนี้

## 6. Acceptance criteria

- [x] Checkpoint PII keys ไม่ถูก restore เข้า memory
- [x] Non-dict samples และ invalid sequence types ไม่ถูก restore
- [x] Non-monotonic sample sequences ไม่ถูก restore
- [x] `last_sequence` mismatch ไม่ถูก restore
- [x] Existing restart, stale temp, corrupt JSON และ malformed state tests ยังผ่าน
- [x] Physical power cut, disk-full และ Acer recovery ยังคงระบุ `UNVERIFIED`
- [ ] Phase-end hardening gate และ master regression หลัง commit ใหม่
- [ ] Release-freeze refresh หลัง commit ใหม่

## 7. Evidence paths

- `edge_runtime.py`
- `power_loss_recovery_harness.py`
- `test_edge_runtime.py`
- `test_p0_recovery.py`
- `test_power_loss_recovery_harness.py`
- `P0_POWER_LOSS_SOFTWARE_EVIDENCE.json`
- `P0_PHASE_HANDOFF.md`
- `P0_STATUS_REPORT.md`
- `tasks.md`
