# P2-002 Serial Bench Evidence Contract Hardening Report

**วันที่:** 21 สิงหาคม 2026 (GMT+7)
**Task ID:** `P2-002-SBE-001`
**สถานะ:** `Applied` → software phase-end verification ผ่าน; physical Acer bench ยังไม่เริ่ม
**Owner role:** Edge architect + security auditor

## 1. ขอบเขตและเหตุผล

รอบนี้เพิ่ม evidence contract สำหรับ Serial bench runner โดยไม่เปิด serial port จริงและไม่อ้างผลจาก Acer Spin N17H2 การเปลี่ยนแปลงทำให้ dry-run และ physical-loopback output มี schema ที่ตรวจสอบได้, canonical SHA-256 binding, redaction boundary และสถานะ S-001 ถึง S-015 ที่แยก `PASS`, `FAIL`, `NOT_RUN`, `BLOCKED` และ `UNVERIFIED` อย่างชัดเจน

Evidence contract นี้มีไว้เตรียมรับผลทดสอบจริงในห้องทดลอง ไม่ใช่การสร้างหลักฐานทางกายภาพแทนการทดสอบจริง

## 2. Controls ที่ implement

| Control | พฤติกรรมที่ตรวจสอบได้ | สถานะ |
|---|---|---|
| Contract version | ทุก record ถูกผูกด้วย `serial-bench-evidence-v1` | Implemented |
| Test coverage | `tests` ต้องครอบคลุม exactly `S-001` ถึง `S-015` | Implemented |
| Redaction boundary | `patient_data_used`, `private_key_used`, `raw_frames_recorded` ต้องเป็น `false` | Implemented |
| Forbidden marker scan | ปฏิเสธ patient identity, bearer, secret, private key และ API-key markers ใน values | Implemented |
| Physical claim gate | `PASSED` ต้องเป็น physical loopback, มี explicit confirmation, `S-003=PASS` และ hardware state `VERIFIED` | Implemented |
| Dry-run claim gate | dry-run อ้างได้เฉพาะ `DRY_RUN_ONLY`, hardware `PENDING` และ confirmation `false` | Implemented |
| Production boundary | `production_network_validation` ไม่สามารถถูกตั้งเป็น `VERIFIED` โดย runner นี้ | Implemented |
| Evidence integrity | canonical SHA-256 hash ครอบคลุม payload โดยตัดเฉพาะ field hash ออกจาก input | Implemented |
| Shell safety | runner ไม่มี shell execution path | Verified by phase-end gate |
| Physical fail-closed | ไม่มี port/confirmation/dependency/IO failure จะไม่ถูกแปลงเป็น physical pass | Implemented |

## 3. Verification evidence

| Test/gate | ผล |
|---|---|
| `test_serial_bench_runner.py` | PASS |
| `test_serial_bench_evidence_contract.py` | PASS |
| PII/secret/coverage/hash tamper rejection | PASS |
| Physical PASS confirmation/S-003 binding | PASS |
| `test_p2_002_serial_evidence_phase_end_hardening.py` | PASS |
| Dry-run physical claim boundary | PASS |
| No shell execution static check | PASS |
| Private-key block scan | PASS |
| `git diff --check` | PASS |

## 4. สิ่งที่ evidence record จะบอกได้

เมื่อใช้ `--dry-run`, record จะรายงาน `status=DRY_RUN_ONLY`, `physical_hardware_validation=PENDING`, `production_network_validation=PENDING`, `physical_confirmation_verified=false` และ `S-004=PASS` จาก codec self-check เท่านั้น

เมื่อ physical loopback ผ่านจริง record จึงจะสามารถรายงาน `status=PASSED` ได้ต่อเมื่อมี explicit non-production confirmation, `S-003=PASS`, `physical_hardware_validation=VERIFIED` และ hash ที่คำนวณใหม่ตรงกับ payload ทั้งหมด หาก physical run ถูก block หรือ fail จะไม่สามารถคง hardware state เป็น `VERIFIED`

## 5. Rollback และ stop conditions

Rollback ทำได้โดย revert `serial_bench_evidence_contract.py`, `serial_bench_runner.py`, tests, phase-end gate, `run_all_tests.py`, report นี้ และ backlog notes จากนั้นต้อง rerun focused tests, master regression และ release-freeze alignment

ต้องหยุดทันทีหาก evidence มี raw frame, patient identity, production bearer, private key, unexplained serial traffic, unknown driver, production network, real patient/device pairing หรือผู้ปฏิบัติงานพยายามใช้ dry-run เป็น physical evidence

## 6. Claim boundary

ผลนี้เป็น **software framing/evidence-contract verification** เท่านั้น ไม่ใช่ Acer hardware validation, COM enumeration proof, driver validation, USB-serial loopback proof, disconnect/reconnect proof, Device Trust physical handoff, queue-pressure bench result, power-loss evidence, clinical validation หรือ production transport authorization

P2-002 ยังคงเป็น **In Progress**. สถานะโครงการยังเป็น **controlled production prototype**, **P0-hardened software baseline**, **pilot-ready foundation** และ **clinical validation pending**

## 7. Evidence paths

- `serial_bench_evidence_contract.py`
- `serial_bench_runner.py`
- `test_serial_bench_runner.py`
- `test_serial_bench_evidence_contract.py`
- `test_p2_002_serial_evidence_phase_end_hardening.py`
- `P2_EDGE_IOT_ADAPTER_READINESS_REPORT.md`
- `SERIAL_BENCH_VALIDATION_PLAN.md`
- `tasks.md`
