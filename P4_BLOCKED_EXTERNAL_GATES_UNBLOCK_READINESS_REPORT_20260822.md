# P4 Blocked External Gates — Unblock Readiness Report

**โครงการ:** Smart Ward Hub Reconcile
**วันที่ตรวจ:** 22 สิงหาคม 2026
**P4 Decision:** `P4_BLOCKED_GATE_UNBLOCK_READINESS_RECONCILED`
**ขอบเขต:** local-only, read-only, evidence-bounded readiness matrix สำหรับ 7 External Gates ที่ยังอยู่ในสถานะ `BLOCKED`

## 1. สรุปผู้บริหาร

P4 ตรวจสอบ 7 Gate ที่ยังถูกบล็อก โดย cross-check current status reconciliation, blocker analysis, required external evidence, owner action, stop condition และ freeze binding. ผลคือ blocker records ทั้ง 7 รายการครบถ้วนและสอดคล้องกับ current matrix: `7 BLOCKED / 3 OPEN / 0 EVIDENCE_SUBMITTED`

P4 ไม่ได้ปลดล็อก Gate ใดและไม่เปลี่ยนสถานะภายนอก เนื่องจากเงื่อนไขของทั้ง 7 Gate ต้องอาศัย external owner, โรงพยาบาล, independent reviewer, real integration, physical hardware หรือ external trust service ตาม domain ที่เกี่ยวข้อง

## 2. สถานะรวม

| รายการ | ผลตรวจ |
|---|---|
| Blocked Gate records | 7 รายการครบ |
| Current blocked IDs | GV-01, GV-03, GV-04, GV-06, GV-07, GV-08, GV-09 |
| Current open IDs | GV-02, GV-05, GV-10 |
| Current evidence submitted | 0 |
| P4 decision | `P4_BLOCKED_GATE_UNBLOCK_READINESS_RECONCILED` |
| Remediation codes | ว่าง |
| Unblock authorized | `false` |
| Ready for external review | `false` |
| External transmission | `false` |
| Runtime mutation | `false` |
| Production ready | `false` |
| Hardware evidence | `UNVERIFIED` |

## 3. เงื่อนไขปลดล็อกแต่ละ Gate

### GV-01 — Clinical Governance & Protocol

**Owner:** `clinical_owner`
**Severity:** Critical
**Status:** `BLOCKED`
**Required evidence:** `approved_protocol`, `consent_or_waiver`, `signed_scope`

ต้องแต่งตั้ง Clinical Owner หรือคณะกรรมการที่มีอำนาจ อนุมัติ institutional clinical protocol, กำหนด signed scope of study และมี consent หรือ waiver decision ที่ได้รับอนุมัติอย่างเป็นทางการ จึงจะพิจารณาเปิด Gate ได้

Stop condition คือห้ามเริ่ม interventional หรือ clinical validation activity กับผู้ป่วยจริงก่อนมี signed governance scope และ approval ที่เกี่ยวข้อง Software readiness plan ไม่สามารถแทน ethics หรือ clinical governance approval ได้

### GV-03 — HIS / Admission Integration

**Owner:** `integration_owner`
**Severity:** High
**Status:** `BLOCKED`
**Required evidence:** `real_his_transcript`, `fhir_ack_reconciliation`, `failure_recovery`

ต้องมี isolated real-HIS sandbox session ที่ได้รับอนุมัติ พร้อม transcript ของ admission flow, structured FHIR acknowledgement/reconciliation และ failure-recovery evidence. ต้องกำหนด integration boundary, rollback plan และผู้รับผิดชอบก่อนเชื่อมต่อจริง

P0 HIS contract tests และ Zero-PII tokenization เป็นเพียง software contract simulation ยังไม่ใช่ real HIS evidence และห้ามส่ง admission data ไปยัง HIS จริงจากหลักฐาน simulation เพียงอย่างเดียว

### GV-04 — OIDC / mTLS Identity Transport

**Owner:** `security_owner`
**Severity:** Critical
**Status:** `BLOCKED`
**Required evidence:** `real_oidc_validation`, `real_mtls_handshake`, `key_rotation_transcript`

ต้องมี real IdP discovery และ token-claims validation ใน environment ที่แยกขอบเขต, real mTLS handshake ระหว่าง Fixed Hub กับปลายทาง และ certificate/key rotation transcript ที่ตรวจสอบย้อนกลับได้

ห้ามเปิดรับ real credentials หรือ production identity transport จาก unit test หรือ simulator และห้ามถือ software security/config tests เป็นหลักฐานว่า IdP/mTLS จริงผ่านแล้ว

### GV-06 — Hardware Recovery & Serial Loopback

**Owner:** `reliability_owner`
**Severity:** High
**Status:** `BLOCKED`
**Required evidence:** `serial_loopback_s015`, `power_loss_drill`, `disk_full_drill`

ต้องมี non-production USB-Serial loopback fixture, ยืนยัน COM-port enumeration บน Acer Spin N17H2, รัน physical Serial S-015 framing/partial-read drill และทดสอบ power-loss กับ disk-full recovery ตามแผน

ต้องมี fixture isolation และ operator confirmation `I_HAVE_A_NONPRODUCTION_LOOPBACK` ก่อน physical bench. Software Serial profile, framing test และ pressure simulation ไม่สามารถปลด physical Gate ได้

### GV-07 — Independent WORM Forensic Anchor

**Owner:** `forensic_owner`
**Severity:** High
**Status:** `BLOCKED`
**Required evidence:** `external_worm_receipt`, `trusted_timestamp`, `cross_boundary_verify`

ต้องเชื่อมต่อ independently managed append-only/WORM anchor ภายนอก, ได้ receipt identity, trusted timestamp และทำ cross-boundary readback/verification โดยผู้รับผิดชอบที่แยกจาก local FileAnchorStore

P1-004 FileAnchorStore และ simulated receipt เป็น software preparation เท่านั้น ห้ามอ้างว่าเป็น WORM, tamper-proof หรือ external immutability ก่อนมีหลักฐานภายนอกจริง

### GV-08 — Manufacturer Device Trust & Keys

**Owner:** `security_owner`
**Severity:** Critical
**Status:** `BLOCKED`
**Required evidence:** `manufacturer_provenance`, `hardware_key_custody`, `revocation_distribution`

ต้องมี manufacturer provenance ของอุปกรณ์, hardware key ceremony/custody, dual-control provisioning, rotation, revocation distribution และ lost-device handling evidence ที่ตรวจสอบได้

Key custody contract และ software lifecycle tests ยืนยันได้เฉพาะ contract behavior ไม่ใช่ hardware root-of-trust หรือหลักฐานว่ากุญแจถูกฝังใน Secure Element ของอุปกรณ์จริง

### GV-09 — Clinical Operations & Fallback SOP

**Owner:** `ward_manager`
**Severity:** High
**Status:** `BLOCKED`
**Required evidence:** `staff_training`, `manual_fallback_sop`, `alarm_fatigue_review`

ต้องมี staff training sign-off, manual fallback SOP ที่ได้รับอนุมัติ, alarm-fatigue review และ incident escalation/stop roster สำหรับ ward operation ก่อนเริ่ม controlled pilot

Operations runbook, safe reset workflow และ clinical shadow-mode contract เป็น software/operational preparation ไม่ใช่หลักฐานว่าพยาบาลผ่านการฝึกหรือ SOP ได้รับการอนุมัติจริง

## 4. เงื่อนไขร่วมของการปลดล็อก

ทุก Gate ที่ `BLOCKED` ต้องมี external evidence ที่ตรงกับ required evidence list, owner action ที่ตรวจสอบได้, blocker reason ที่ปิดอย่างเป็นทางการ และต้องเรียก `reopen(reason)` ก่อนส่ง evidence ใหม่ตาม transition contract ใน `external_validation_package.py` การส่ง evidence ไม่ทำให้สถานะเป็น `PASSED` โดยอัตโนมัติ และต้องมี reviewer/authority ตาม domain เป็นผู้ตัดสิน

| Control | P4 requirement |
|---|---|
| Evidence identity | reference ต้องไม่เป็น raw identity, secret หรือ personal contact |
| Evidence completeness | required evidence ต้องครบตาม Gate |
| Owner accountability | owner role และ external action ต้องระบุชัด |
| Reopen rule | `reopen(reason)` ก่อน submission; reason ห้ามว่าง |
| Status semantics | `EVIDENCE_SUBMITTED` ไม่เท่ากับ `PASSED` |
| Authorization | local software ห้าม promote external/clinical/production authority |
| Stop rules | ต้องคง stop condition จน evidence ภายนอกตรวจรับแล้ว |
| Freeze integrity | blocker analysis ต้อง hash-bound กับ release freeze |

## 5. สิ่งที่ repository ทำได้แล้วและยังทำไม่ได้

Repository ทำได้แล้วในระดับ local คือจัดเก็บ blocker matrix, required evidence, owner/action/stop condition, software evidence references, redaction checks, freeze binding และ fail-closed status reconciliation. Repository ยังทำไม่ได้และไม่ควรจำลองเป็นของจริง ได้แก่ ethics/clinical approval, hospital DPO decision, real HIS/IdP/mTLS, COM-port/physical recovery, external WORM/timestamp, manufacturer key custody และ staff training sign-off

> P4 ที่ผ่านหมายถึง **unblock readiness matrix ถูก reconcile และไม่พบข้อมูล blocker ที่ขัดกัน** ไม่ได้หมายถึง 7 External Gates ถูกปลดล็อก

## 6. หลักฐานอ้างอิง

- `p4_blocked_gate_unblock_readiness.py`
- `test_p4_blocked_gate_unblock_readiness.py`
- `test_p4_blocked_gate_unblock_readiness_phase_end_hardening.py`
- `export_p4_blocked_gate_unblock_readiness.py`
- `evals/micro_rag/evidence/p4-blocked-gate-unblock-readiness-local.json`
- `evals/micro_rag/evidence/controlled-pilot-blocker-analysis-20260820.json`
- `evals/micro_rag/evidence/p3-external-gate-status-reconciliation-local.json`
- `external_validation_package.py`

สถานะผลิตภัณฑ์ยังเป็น `CONTROLLED_PRODUCTION_PROTOTYPE` และ `NOT_PRODUCTION_READY`
