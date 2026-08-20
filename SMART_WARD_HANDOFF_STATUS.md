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
| GV-10 Evidence simulation | `simulate_gv10_submission.py` accepted 5 real repository artifacts for review, rejected 10/10 fail-closed mutations, and preserved clinical/production authorization as false |
| GV-10 presentation | Created Thai deck in `gv10_presentation_deck/`; status matrix records 7 BLOCKED, 3 OPEN, 0 PASSED |
| P1-008 Independent review operations | `independent_review_operations.py` and tests implement OPEN/CLOSED lifecycle, finding severity, traceability and post-close mutation lock; dry-run complete, external review not started |
| P2-004 Registry/index hardening | DocumentRegistry v2 and RebuildableIndex v2 add deterministic snapshot/hash verification, lifecycle guards, stale-index detection, atomic rebuild and chunk provenance; software regression passed |
| P2-004 Persistence governance | `persistence_contract.py` validates owner/custodian separation, retention, encryption, backup, raw-identity and external-approval boundaries; local synthetic policy is software-verified only |
| P2-004 Repeated samples | `repeated_sample_evaluation.py` validates compatible provenance and separates provider failures from quality denominator; current live reports are `INSUFFICIENT_SAMPLES` with one sample per model |
| P2-004 Runtime readiness | `runtime_semantic_retrieval_readiness.py` preflight reports `NOT_READY` because runtime backend, access enforcement, external persistence approval, repeated samples and clinical governance are absent; clinical/production authorization remains false |
| P2-004 Review protocol | `P2_004_REPEATED_SAMPLE_PROTOCOL.md`, `p2_004_review_decision.py` and tests enforce minimum 2 compatible samples, provider/quality separation and fail-closed review statuses |
| P2-004 Controlled pilot handoff | `controlled_pilot_handoff.py` and `P2_004_EXTERNAL_REVIEW_COORDINATION_PACKAGE.md` produce `BLOCKED_INCOMPLETE_EVIDENCE`, `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`, 7 blocked gates and 3 open gates |
| Controlled pilot operations | `controlled_pilot_operations.py` validates blockers, artifact SHA-256 manifest, redaction/provenance fields and signed-style non-cryptographic receipt; current operations decision remains blocked |
| Controlled pilot reviewer package | `CONTROLLED_PILOT_OPERATIONS_GATE.md`, `CONTROLLED_PILOT_OPERATIONS_REVIEW_CHECKLIST.md` and operations JSON report provide stop conditions and evidence export checklist |
| Blocker analysis | `analyze_controlled_pilot_blockers.py` verifies 7 blocked gates, 6/6 manifest checks and produces evidence-bounded gap analysis; all external evidence remains `NOT_VERIFIED` |
| External Authorization plan | `EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md` defines 5 waves, owners, dependencies, required external evidence and stop conditions |
| Controlled-Pilot presentation | `controlled_pilot_presentation_deck/` contains a 10-slide Thai status, blocker and unblock-plan deck; presentation URI is `manus-slides://2IHfbcY71J89LypphjWIKt` |
| Wave 0 governance | `WAVE_0_GOVERNANCE_CONTRACT.md`, `wave0_governance.py` and `WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md` validate role, scope, test-window, stop-authority and local freeze structure; external verification remains pending |
| Wave 0 handoff report | `WAVE_0_GOVERNANCE_HANDOFF_REPORT.md` and `wave0-governance-handoff-20260820.json` report `GOVERNANCE_PACKAGE_READY_FOR_EXTERNAL_REVIEW` locally with manifest `12d14f928a701bc2d1148cab48282c8cd71d305ff97624a8d580d5545c311b3a`; authority remains `NONE` |
| P2-004 Model rerun | Runner now uses registry-backed index; Gemini 2.5 index-backed run is 0/8 with 8 provider 429; Gemini 3 index-backed run is 6/8 with 2 provider 429 and 0 quality/adapter rejection |

## Verification evidence

Latest targeted regression หลัง P2-004 continuation ผ่าน persistence contract, repeated-sample aggregation, review decision/handoff, registry/index, response adapter, registry-backed evaluation, runtime readiness, controlled-pilot operations และ blocker analysis tests. Master regression ล่าสุดผ่าน exit code `0` และผลทั้งหมดเป็น software/deterministic simulation evidence ไม่ใช่ clinical validation

Blocker analysis ล่าสุดยืนยัน 7/7 expected blockers, 10/10 gate registry status, 6/6 manifest checks และ no-authorization fields. Wave 0 local governance validator ผ่าน schema/freeze checks และเปิดได้สูงสุดเพียง `GOVERNANCE_PACKAGE_READY_FOR_EXTERNAL_REVIEW`; External Authorization ยังไม่สามารถขออนุมัติจาก software ได้ ต้องมี external owners/reviewer, signed scope, test-window approval และ custody verification จริง.

Controlled-pilot operations report มี 4 artifact entries, SHA-256 manifest hash และ signed-style receipt ที่ระบุชัดว่า `SIMULATED_RECEIPT_NOT_CRYPTOGRAPHIC_SIGNATURE` และ `external_authority=NONE`. รายงานนี้ใช้สำหรับ evidence coordination เท่านั้น

ผลดังกล่าวเป็น **software test evidence และ deterministic simulation evidence** เท่านั้น ไม่ใช่หลักฐานจาก COM port จริง, sensor จริง, production network, HIS จริง หรือ clinical setting. ในผล master suite เองมีข้อความกำกับว่า Phase 6, Device Trust, ward workflow, outside-in admission และ roaming เป็น software tests ไม่ใช่ clinical, HIS หรือ hardware validation

### Micro-RAG v2 model evidence

The current registry/index-backed evidence register records `gemini-2.5-flash` revision `001` at `0/8` because all calls were provider HTTP `429`, and `gemini-3-flash-preview` revision `3-flash-preview-12-2025` at `6/8` with two provider HTTP `429` cases and zero quality/adapter rejection. The earlier fixture-direct 8/8 result remains bounded to its earlier retrieval path and must not be conflated with current index-backed evidence. Repeated-sample aggregation is `INSUFFICIENT_SAMPLES` for both current model paths, runtime readiness is `NOT_READY`, and human review/clinical retrieval remain pending.

## GitHub publication

Repository เป็น **private repository** ที่ [icezingza/smart-ward-hub](https://github.com/icezingza/smart-ward-hub) โดย branch `main` ต้องอ้างอิง commit ล่าสุดจาก `git log` หลังการเผยแพร่แต่ละครั้ง. ก่อนเผยแพร่มีการตรวจ staged tree ไม่พบ runtime database, audit log, private-key markers, credential file หรือ large runtime artifact ที่ควรอยู่ภายนอก Git

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
| GV-10 independent review | เปิด | แต่งตั้ง independent reviewer, signed evidence export, reproduce tests และ finding closure |
| Clinical validation | เปิด | clinical shadow-mode, reviewer sign-off และ safety governance |
| External forensic anchoring | เปิด | append-only external anchor และ operational recovery evidence |
| Key custody | เปิด | ownership, rotation, revocation และ secure storage contract |
| Rate limiting/host hardening | เปิด | enforcement บน deployment target และ operational monitoring |
| Power-loss testing | เปิด | controlled interruption, WAL recovery, filesystem and backup/restore evidence |
| BMAX roaming UI | Deferred | อยู่หลัง priority matrix; Fixed Hub ยังเป็น authority |
| P2-004 runtime semantic retrieval | เปิด | persistence owner/retention/access approval, at least two compatible model samples, runtime backend/access enforcement, human review, clinical retrieval governance and external gate review; local readiness remains NOT_READY and pilot handoff BLOCKED |
| NEWS/MEWS clinical adapter | Proposed | ต้องมี clinical governance ก่อนเปิดใช้ |

## Product claim boundary

จุดขายที่ควรรักษาไว้คือ **Sovereign Edge / Offline-first**, **Zero-PII**, **Patient Safety Intelligence**, **Tamper-Evident Evidence**, **HIS/EMR Interoperability**, **Device Trust & Secure Provisioning**, **Outside-in Ward Workflow** และ **Sovereign Ward Operating Layer**

ในเอกสารและการสื่อสารภายนอกควรใช้คำว่า **controlled production prototype**, **functional verification passed**, **pilot-ready foundation**, **clinical validation pending**, **P0-hardened software baseline** และ **pilot deployment configuration pending**. ห้ามใช้คำว่า **clinical-ready**, **tamper-proof**, **HIPAA/PDPA compliant 100%** หรือ **production-ready** โดยอาศัย functional tests เพียงอย่างเดียว

## เอกสารอ้างอิงภายใน repository

เอกสารสำคัญสำหรับ handoff ได้แก่ [README.md](README.md), [P2_EDGE_IOT_ADAPTER_READINESS_REPORT.md](P2_EDGE_IOT_ADAPTER_READINESS_REPORT.md), [SERIAL_BENCH_VALIDATION_PLAN.md](SERIAL_BENCH_VALIDATION_PLAN.md), [ACER_BENCH_READONLY_INVENTORY.md](ACER_BENCH_READONLY_INVENTORY.md), [NETWORK_PRESSURE_SIMULATION_REPORT.md](NETWORK_PRESSURE_SIMULATION_REPORT.md), [P0_STATUS_REPORT.md](P0_STATUS_REPORT.md), [ZERO_TRUST_TRUST_BOUNDARIES.md](ZERO_TRUST_TRUST_BOUNDARIES.md), [MICRO_RAG_V2_RERUN_EVIDENCE.md](evals/micro_rag/evidence/MICRO_RAG_V2_RERUN_EVIDENCE.md), [P0_PHASE_HANDOFF.md](P0_PHASE_HANDOFF.md), [BACKUP_RESTORE_CONTRACT.md](BACKUP_RESTORE_CONTRACT.md), [P1_HOST_HARDENING_CHECKLIST.md](P1_HOST_HARDENING_CHECKLIST.md), [OPERATIONAL_TRUNK_HANDOFF.md](OPERATIONAL_TRUNK_HANDOFF.md), [KEY_CUSTODY_PROVISIONING_CONTRACT.md](KEY_CUSTODY_PROVISIONING_CONTRACT.md), [P1_DEVICE_TRUST_HANDOFF.md](P1_DEVICE_TRUST_HANDOFF.md), [P1_003_KEY_CUSTODY_TEST_REVIEW.md](P1_003_KEY_CUSTODY_TEST_REVIEW.md), [P1_004_EXTERNAL_ANCHOR_CONTRACT.md](P1_004_EXTERNAL_ANCHOR_CONTRACT.md), [P1_004_HANDOFF.md](P1_004_HANDOFF.md), [FILE_ANCHOR_STORE_PRODUCTION_GAP_REVIEW.md](FILE_ANCHOR_STORE_PRODUCTION_GAP_REVIEW.md), [P1_005_CLINICAL_SHADOW_MODE_CONTRACT.md](P1_005_CLINICAL_SHADOW_MODE_CONTRACT.md), [P1_005_CLINICAL_SHADOW_REVIEW.md](P1_005_CLINICAL_SHADOW_REVIEW.md), [P1_005_ZERO_PII_AND_NON_ACCURACY_METRICS.md](P1_005_ZERO_PII_AND_NON_ACCURACY_METRICS.md), [P1_006_CLINICAL_VALIDATION_READINESS_PLAN.md](P1_006_CLINICAL_VALIDATION_READINESS_PLAN.md), [P1_007_EXTERNAL_VALIDATION_COORDINATION_PACKAGE.md](P1_007_EXTERNAL_VALIDATION_COORDINATION_PACKAGE.md), [GV10_INDEPENDENT_REVIEW_DOSSIER.md](GV10_INDEPENDENT_REVIEW_DOSSIER.md), [GV10_SUBMISSION_CHECKLIST.md](GV10_SUBMISSION_CHECKLIST.md), [GV10_SIMULATION_REPORT.md](GV10_SIMULATION_REPORT.md), [P1_008_INDEPENDENT_REVIEW_OPERATIONS.md](P1_008_INDEPENDENT_REVIEW_OPERATIONS.md), [P2_004_REGISTRY_INDEX_HARDENING_PLAN.md](P2_004_REGISTRY_INDEX_HARDENING_PLAN.md), [P2_004_PERSISTENCE_OWNERSHIP_CONTRACT.md](P2_004_PERSISTENCE_OWNERSHIP_CONTRACT.md), [P2_004_REPEATED_SAMPLE_PROTOCOL.md](P2_004_REPEATED_SAMPLE_PROTOCOL.md), [P2_004_EXTERNAL_REVIEW_COORDINATION_PACKAGE.md](P2_004_EXTERNAL_REVIEW_COORDINATION_PACKAGE.md), [CONTROLLED_PILOT_OPERATIONS_GATE.md](CONTROLLED_PILOT_OPERATIONS_GATE.md), [CONTROLLED_PILOT_OPERATIONS_REVIEW_CHECKLIST.md](CONTROLLED_PILOT_OPERATIONS_REVIEW_CHECKLIST.md), [CONTROLLED_PILOT_BLOCKER_ANALYSIS.md](CONTROLLED_PILOT_BLOCKER_ANALYSIS.md), [EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md](EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md), [CONTROLLED_PILOT_PRESENTATION_OUTLINE.md](CONTROLLED_PILOT_PRESENTATION_OUTLINE.md), [WAVE_0_GOVERNANCE_CONTRACT.md](WAVE_0_GOVERNANCE_CONTRACT.md), [WAVE_0_GOVERNANCE_HANDOFF_REPORT.md](WAVE_0_GOVERNANCE_HANDOFF_REPORT.md), [WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md](WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md), [P2_004_HARDENING_EVIDENCE.md](P2_004_HARDENING_EVIDENCE.md),
 [evals/micro_rag/evidence/MICRO_RAG_V2_RERUN_EVIDENCE.md](evals/micro_rag/evidence/MICRO_RAG_V2_RERUN_EVIDENCE.md), [tasks.md](tasks.md)
