# Smart Ward Hub — Handoff Status

**วันที่รายงาน:** 20 สิงหาคม 2026

## สรุปผู้บริหาร

Smart Ward Hub อยู่ในสถานะ **controlled production prototype** และมี **P0-hardened software baseline** ที่ผ่าน **functional verification** ใน sandbox แล้ว ระบบได้รับการเตรียมสำหรับ pilot ในเชิงสถาปัตยกรรมและ software contract แต่ยังมีสถานะ **pilot deployment configuration pending** และ **clinical validation pending**

การดำเนินงานรอบนี้ได้เตรียม physical-bench handoff สำหรับ Acer Spin N17H2 ในรูปแบบที่ fail-closed โดยไม่เปิด COM port จริงและไม่ส่งข้อมูลใด ๆ ออกจากเครื่อง การตรวจ Acer ทำแบบ read-only พบ Windows 11 Pro build `26200`, Python `3.14.3`, ไม่พบ `Win32_SerialPort`/COM device ที่ enumerate อยู่ และยังไม่พบ workspace ของ Smart Ward Hub ที่ตำแหน่ง Windows ที่ตรวจสอบ ดังนั้น physical Serial bench ยังมีสถานะ **NOT_STARTED** อย่างถูกต้อง

## งานที่ดำเนินการเสร็จในรอบนี้

| รายการ | ผลลัพธ์ |
|---|---|
| Serial bench runner | เพิ่ม `serial_bench_runner.py` แบบ cross-platform, dry-run-first และ fail-closed |
| Safety regression | เพิ่ม `test_serial_bench_runner.py`; dry-run, explicit confirmation gate และ phrase check ผ่านทั้งหมด |
| Master regression integration | ลงทะเบียน Serial bench runner safety test ใน `run_all_tests.py` |
| Runtime hygiene | เพิ่ม ignore สำหรับ `serial_bench_evidence.json` และลบ database, audit log, simulation output และ bytecode ออกจาก workspace ก่อน commit |
| Acer inventory | บันทึกผล read-only ใน `ACER_BENCH_READONLY_INVENTORY.md` |
| Bench procedure | อัปเดต `SERIAL_BENCH_VALIDATION_PLAN.md` ด้วยคำสั่ง safe runner และ physical gate |
| P2 readiness | อัปเดต `P2_EDGE_IOT_ADAPTER_READINESS_REPORT.md` ให้สะท้อน runner evidence และ no-COM-port gate |
| Repository documentation | เพิ่ม `README.md` ที่กำหนด product boundary, differentiators และ evidence limits |
| GitHub publication | สร้างและ push ไปยัง private repository `icezingza/smart-ward-hub` |
| P2-004 Micro-RAG | Deterministic baseline, registry/index baseline และ model-agnostic adapter ผ่าน; Gemini 3 Flash v2 ผ่าน 8/8; Gemini 2.5 pinned rerun ได้ 2/8 โดย 6 calls ติด HTTP 429 |
| P0-001 HIS/Admission Gateway | Sandbox contract test ผ่าน tokenization, TTL, revocation, idempotency และ structured acknowledgment; hospital integration ยังเปิด |
| P0-004 Recovery | Software fault harness ผ่าน checkpoint/WAL/malformed-state scenarios; physical power-loss/storage gate ยังเปิด |
| P1-001 Backup/restore | SQLite backup API, manifest/checksum, isolated restore, tamper detection และ secret-boundary regression ผ่าน; real destination/retention ยังเปิด |
| P1-002 Host/deployment | Readiness validator, Windows Acer auto-run template และ host-hardening checklist เตรียมแล้ว; Acer execution ยังไม่เริ่ม |
| P1-003 Device Trust custody | Dual-control, rotation, terminal revocation, lost-device และ private-key exclusion software contract ผ่าน; manufacturer CA/HSM/secure element ยังเปิด |
| P1-004 External anchor | Receipt identity, idempotency, append-only delete refusal, tamper detection และ fault matrix ผ่าน; independent WORM service ยังเปิด |
| FileAnchorStore hardening | Input validation, source-tree path rejection, record hash, local receipt, idempotent replay และ readback verification ผ่าน; host ACL/external immutability ยังเปิด |
| P1-005 Clinical shadow-mode | Policy gates, safe labels, Zero-PII marker boundary, review timing, denominator-labelled metrics และ stop/resume controls ผ่าน; clinical governance ยังเปิด |
| P1-006 Clinical validation readiness | Fail-closed preflight contract distinguishes NOT_READY from READY_FOR_EXTERNAL_GOVERNANCE_REVIEW; real-world authorization remains false |
| P1-007 External validation coordination | Ten named external gates, owner/evidence requirements, blocker visibility and no-authorization boundary implemented; external review not started |

## Verification evidence

Latest master regression หลังเพิ่ม P1-007 รันจบด้วย exit code `0` และผ่าน test groups สำหรับ Phase 1–6, P0 HIS/Admission Gateway contract, P0 recovery fault harness, P1 backup/restore, deployment readiness, Device Trust, Ward Workflow, Outside-in Admission, Roaming synchronization, Micro-RAG baseline, P2-002 adapters, Serial framing, network-pressure simulation, Serial bench runner safety, residual controls, P1-005/P1-006 governance tests, P1-007 external-validation package, reliability และ 30-day pilot simulation

ผลดังกล่าวเป็น **software test evidence และ deterministic simulation evidence** เท่านั้น ไม่ใช่หลักฐานจาก COM port จริง, sensor จริง, production network, HIS จริง หรือ clinical setting. ในผล master suite เองมีข้อความกำกับว่า Phase 6, Device Trust, ward workflow, outside-in admission และ roaming เป็น software tests ไม่ใช่ clinical, HIS หรือ hardware validation

### Micro-RAG v2 model evidence

The current corpus-v2 eight-case prompt passed `8/8` through `response-adapter-v1` for live-catalog-verified `gemini-3-flash-preview` revision `3-flash-preview-12-2025`, with redaction passing and runtime authority `NONE`. A separate current-prompt run against the pinned `gemini-2.5-flash` revision `001` passed `2/8`; six later provider calls returned HTTP `429`. The Gemini 3 result is valid only for that model/revision and does not close the pinned Gemini 2.5 rerun gate. Runtime semantic retrieval, human review and clinical retrieval remain pending.

## GitHub publication

Repository ถูกสร้างเป็น **private repository** และ push สำเร็จไปที่ [icezingza/smart-ward-hub](https://github.com/icezingza/smart-ward-hub) โดย branch `main` อยู่ที่ commit ล่าสุด `77c6da5` ซึ่งรวม P1-005 review/metrics hardening, P1-006 clinical-validation readiness preflight และ handoff ที่อัปเดตแล้ว ก่อนเผยแพร่มีการตรวจ staged tree ไม่พบ runtime database, audit log, private-key markers, credential file หรือ large runtime artifact ที่ควรอยู่ภายนอก Git

## Physical Acer Serial bench — เงื่อนไขก่อนเริ่ม

ยังห้ามเริ่ม physical test จนกว่าจะครบเงื่อนไขต่อไปนี้: ต้องมี USB-serial loopback fixture หรือ controlled gateway ที่ไม่ใช่ production; ต้องติดตั้ง project และ dependencies บน Acer; ต้องมี COM port ที่ตรวจสอบได้; ต้องแยก fixture ออกจาก patient device และ production network; และ operator ต้องยืนยันว่าไม่มี patient data ถูกใช้

คำสั่งที่ปลอดภัยในขั้นปัจจุบันคือ:

```bash
python serial_bench_runner.py --list-ports
python serial_bench_runner.py --dry-run --output serial_bench_evidence.json
```

เมื่อมี fixture และตรวจสอบพอร์ตแล้วเท่านั้น จึงพิจารณาคำสั่ง physical ต่อไปนี้:

```bash
python serial_bench_runner.py \
  --port COMx \
  --baudrate 115200 \
  --confirm-physical I_HAVE_A_NONPRODUCTION_LOOPBACK \
  --output serial_bench_evidence.json
```

การระบุ `--port` เพียงอย่างเดียวไม่เพียงพอ เพราะ runner จะ block หากไม่มีคำยืนยันตรงตัว `I_HAVE_A_NONPRODUCTION_LOOPBACK`. Runner ไม่บันทึก raw frames และ CRC32 ถูกใช้เพื่อ integrity detection เท่านั้น ไม่ใช่ trust root หรือการยืนยันตัวตนอุปกรณ์

## Gates ที่ยังเปิดอยู่

| Gate | สถานะที่ถูกต้อง | หลักฐานที่ต้องเพิ่ม |
|---|---|---|
| Physical Acer Serial loopback | NOT_STARTED | fixture, COM enumeration, framing, partial read, reconnect และ evidence จากอุปกรณ์จริง |
| HIS/Admission Gateway | เปิด | integration กับระบบจริงและ structured acknowledgement/purge evidence |
| OIDC/mTLS | เปิด | ทดสอบกับ IdP และ certificate lifecycle จริง |
| Hardware/network | เปิด | driver, CPU/memory, cable, reconnect, segmentation และ pressure evidence จริง |
| Clinical validation | เปิด | clinical shadow-mode, reviewer sign-off และ safety governance |
| External forensic anchoring | เปิด | append-only external anchor และ operational recovery evidence |
| Key custody | เปิด | ownership, rotation, revocation และ secure storage contract |
| Rate limiting/host hardening | เปิด | enforcement บน deployment target และ operational monitoring |
| Power-loss testing | เปิด | controlled interruption, WAL recovery, filesystem and backup/restore evidence |
| BMAX roaming UI | Deferred | อยู่หลัง priority matrix; Fixed Hub ยังเป็น authority |
| NEWS/MEWS clinical adapter | Proposed | ต้องมี clinical governance ก่อนเปิดใช้ |

## Product claim boundary

จุดขายที่ควรรักษาไว้คือ **Sovereign Edge / Offline-first**, **Zero-PII**, **Patient Safety Intelligence**, **Tamper-Evident Evidence**, **HIS/EMR Interoperability**, **Device Trust & Secure Provisioning**, **Outside-in Ward Workflow** และ **Sovereign Ward Operating Layer**

ในเอกสารและการสื่อสารภายนอกควรใช้คำว่า **controlled production prototype**, **functional verification passed**, **pilot-ready foundation**, **clinical validation pending**, **P0-hardened software baseline** และ **pilot deployment configuration pending**. ห้ามใช้คำว่า **clinical-ready**, **tamper-proof**, **HIPAA/PDPA compliant 100%** หรือ **production-ready** โดยอาศัย functional tests เพียงอย่างเดียว

## เอกสารอ้างอิงภายใน repository

เอกสารสำคัญสำหรับ handoff ได้แก่ [README.md](README.md), [P2_EDGE_IOT_ADAPTER_READINESS_REPORT.md](P2_EDGE_IOT_ADAPTER_READINESS_REPORT.md), [SERIAL_BENCH_VALIDATION_PLAN.md](SERIAL_BENCH_VALIDATION_PLAN.md), [ACER_BENCH_READONLY_INVENTORY.md](ACER_BENCH_READONLY_INVENTORY.md), [NETWORK_PRESSURE_SIMULATION_REPORT.md](NETWORK_PRESSURE_SIMULATION_REPORT.md), [P0_STATUS_REPORT.md](P0_STATUS_REPORT.md), [ZERO_TRUST_TRUST_BOUNDARIES.md](ZERO_TRUST_TRUST_BOUNDARIES.md), [MICRO_RAG_V2_RERUN_EVIDENCE.md](evals/micro_rag/evidence/MICRO_RAG_V2_RERUN_EVIDENCE.md), [P0_PHASE_HANDOFF.md](P0_PHASE_HANDOFF.md), [BACKUP_RESTORE_CONTRACT.md](BACKUP_RESTORE_CONTRACT.md), [P1_HOST_HARDENING_CHECKLIST.md](P1_HOST_HARDENING_CHECKLIST.md), [OPERATIONAL_TRUNK_HANDOFF.md](OPERATIONAL_TRUNK_HANDOFF.md), [KEY_CUSTODY_PROVISIONING_CONTRACT.md](KEY_CUSTODY_PROVISIONING_CONTRACT.md), [P1_DEVICE_TRUST_HANDOFF.md](P1_DEVICE_TRUST_HANDOFF.md), [P1_003_KEY_CUSTODY_TEST_REVIEW.md](P1_003_KEY_CUSTODY_TEST_REVIEW.md), [P1_004_EXTERNAL_ANCHOR_CONTRACT.md](P1_004_EXTERNAL_ANCHOR_CONTRACT.md), [P1_004_HANDOFF.md](P1_004_HANDOFF.md), [FILE_ANCHOR_STORE_PRODUCTION_GAP_REVIEW.md](FILE_ANCHOR_STORE_PRODUCTION_GAP_REVIEW.md), [P1_005_CLINICAL_SHADOW_MODE_CONTRACT.md](P1_005_CLINICAL_SHADOW_MODE_CONTRACT.md), [P1_005_CLINICAL_SHADOW_REVIEW.md](P1_005_CLINICAL_SHADOW_REVIEW.md), [P1_005_ZERO_PII_AND_NON_ACCURACY_METRICS.md](P1_005_ZERO_PII_AND_NON_ACCURACY_METRICS.md), [P1_006_CLINICAL_VALIDATION_READINESS_PLAN.md](P1_006_CLINICAL_VALIDATION_READINESS_PLAN.md), [P1_007_EXTERNAL_VALIDATION_COORDINATION_PACKAGE.md](P1_007_EXTERNAL_VALIDATION_COORDINATION_PACKAGE.md), [GV10_INDEPENDENT_REVIEW_DOSSIER.md](GV10_INDEPENDENT_REVIEW_DOSSIER.md), [GV10_SUBMISSION_CHECKLIST.md](GV10_SUBMISSION_CHECKLIST.md), [tasks.md](tasks.md)
