# GV-10 — Independent Review Evidence Dossier

**Dossier ID:** `smart-ward-gv10-review-v1`
**สถานะ:** เตรียมเป็น input สำหรับคณะกรรมการตรวจสอบอิสระ; **ยังไม่ใช่ clinical validation และยังไม่ใช่ production approval**

## 1. วัตถุประสงค์และขอบเขต

Dossier นี้รวบรวมหลักฐานของ Smart Ward Hub เพื่อให้ผู้ตรวจสอบอิสระตรวจความถูกต้องของ software controls, simulation evidence, residual risks, claim boundaries และ external-gate blockers โดยผู้ตรวจสอบต้องสามารถตรวจซ้ำจาก artifact ต้นทางและตรวจได้ว่าหลักฐานใดเป็น software-only, simulation-only, external-unverified หรือ clinical-governance-unverified

Dossier ไม่อนุญาตให้ใช้ผล functional test เพียงอย่างเดียวเพื่อสรุปว่าเป็น clinical-ready, tamper-proof, HIPAA/PDPA compliant 100% หรือ production-ready

## 2. Evidence classification ที่ต้องใช้

| Class | ความหมาย | ตัวอย่าง |
|---|---|---|
| `SOFTWARE_VERIFIED` | ทดสอบซ้ำได้จาก source/test ใน sandbox | `test_backup_restore.py`, `test_clinical_validation_readiness.py` |
| `SIMULATION_ONLY` | ผล deterministic simulation ไม่ใช่ field evidence | `network_pressure_result`, 30-day pilot simulation |
| `EXTERNAL_UNVERIFIED` | ต้องยืนยันกับ HIS, IdP, WORM, Acer หรือ hardware จริง | real mTLS transcript, Acer S-001–S-015 |
| `CLINICAL_GOVERNANCE_UNVERIFIED` | ต้องมี clinical owner/committee ลงนาม | protocol, consent/waiver, human-factors review |
| `BLOCKER_RECORD` | หลักฐานอธิบายเหตุที่ gate ยังเปิดหรือ blocked | no COM port, no real HIS, no clinical owner |

## 3. Evidence map จาก P1-001 ถึง P1-006

| Workstream | Artifact ที่ส่งให้ผู้ตรวจ | Class | สิ่งที่ผู้ตรวจต้องตรวจซ้ำ | ขอบเขตที่ยังไม่ปิด |
|---|---|---|---|---|
| P1-001 | `BACKUP_RESTORE_CONTRACT.md`, `backup_restore.py`, `test_backup_restore.py` | SOFTWARE_VERIFIED | SQLite Backup API, manifest checksum, isolated restore, secret rejection | encrypted destination, retention approval, real restore drill |
| P1-002 | `P1_HOST_HARDENING_CHECKLIST.md`, `deployment_readiness.py`, Windows templates | SOFTWARE_VERIFIED | loopback binding, path separation, pilot defaults, no embedded secret | Acer ACL/firewall/patch/service recovery |
| P1-003 | `KEY_CUSTODY_PROVISIONING_CONTRACT.md`, `key_custody_contract.py`, tests | SOFTWARE_VERIFIED | dual control, rotation, revocation, lost state, key exclusion | manufacturer CA, HSM/secure element, hardware provenance |
| P1-004 | `P1_004_EXTERNAL_ANCHOR_CONTRACT.md`, `external_anchor.py`, `edge_controls.py`, tests | SOFTWARE_VERIFIED | receipt identity, idempotency, readback/tamper detection, delete refusal | independent WORM, trusted timestamp, cross-boundary verification |
| P1-005 | `P1_005_CLINICAL_SHADOW_REVIEW.md`, `clinical_shadow_mode.py`, tests | SOFTWARE_VERIFIED | Zero-PII marker boundary, safe labels, review timing, non-accuracy metric semantics, stop/resume | clinical owner, SOP, human factors, alarm fatigue, real shadow run |
| P1-006 | `P1_006_CLINICAL_VALIDATION_READINESS_PLAN.md`, `clinical_validation_readiness.py`, tests | SOFTWARE_VERIFIED | fail-closed 17-gate preflight and no-authorization lock | governance sign-off, consent/waiver, real infrastructure/device qualification |

## 4. GV-10 required submission bundle

ผู้เตรียม dossier ควรส่งชุดข้อมูลแบบ read-only หรือ signed export ที่ประกอบด้วย manifest ของ artifact, SHA-256 ของทุกไฟล์, source commit, test command, timestamp แบบ timezone-aware, environment summary, redaction result, reviewer role และ chain-of-custody reference สำหรับแต่ละรายการ

ห้ามส่ง database runtime, audit log ที่ยังไม่ redact, patient token mapping, private key, mTLS private key, credential, `.env`, crash dump หรือ raw clinical payload เข้า dossier. หากจำเป็นต้องตรวจข้อมูลดังกล่าว ให้ผู้ตรวจสอบใช้ secure review channel ที่องค์กรอนุมัติและบันทึกการเข้าถึงแยกต่างหาก

## 5. Chain-of-custody fields

ทุก `EvidenceEntry` ต้องมี `evidence_id`, `gate_id`, `artifact_ref`, `artifact_sha256`, `evidence_class`, `collected_at_utc`, `prepared_by_role`, `source_boundary`, `redaction_status=PASS` และ `chain_of_custody_ref`. ผู้ตรวจสอบควรตรวจว่า hash ถูกคำนวณก่อนส่ง, artifact ที่ได้รับตรงกับ manifest, commit ไม่เปลี่ยนระหว่าง review และทุกการเปลี่ยน artifact สร้าง evidence ID ใหม่

## 6. GV-10 independent review procedure

ผู้ตรวจสอบอิสระควรเริ่มจากการยืนยัน scope และ claim boundary จากนั้นตรวจ manifest/hash, ทำซ้ำ deterministic tests ที่ระบุ, ตรวจ traceability จาก gate ไปยัง artifact, ตรวจ negative/fail-closed tests, ทบทวน residual risk และแยก software evidence ออกจาก external/clinical evidence ก่อนออก finding

ผลการตรวจควรแบ่งเป็น `ACCEPTED_FOR_REVIEW`, `REQUIRES_CLARIFICATION`, `BLOCKED_EXTERNAL_EVIDENCE` หรือ `REJECTED`. คำว่า accepted ในขั้นนี้หมายถึงรับ artifact เข้าสู่กระบวนการ review เท่านั้น ไม่ใช่การอนุมัติ pilot, clinical validation หรือ production

## 7. Current GV-10 limitations

ปัจจุบันมี software evidence และ deterministic simulation evidence แต่ยังไม่มี real HIS transcript, real OIDC/mTLS transcript, independent WORM receipt, manufacturer hardware provenance, Acer physical serial bench, physical power-loss drill, clinical owner sign-off, consent/waiver, staff training, independent clinical adjudication หรือ real-world shadow-mode data

ดังนั้น dossier ที่สร้างจาก repository ณ เวลานี้ควรใช้เป็น **pre-review package** และต้องแสดง blocker เหล่านี้อย่างเปิดเผยต่อคณะกรรมการตรวจสอบอิสระ
