# Smart Ward Hub — P0 Phase Handoff

**วันที่:** 20 สิงหาคม 2026 (GMT+7)

## สถานะรวม

Smart Ward Hub ยังคงอยู่ในสถานะ **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation**, **pilot deployment configuration pending** และ **clinical validation pending**

เฟสนี้เพิ่มหลักฐาน software/contract validation สำหรับ P0-001 และ P0-004 โดยไม่ปิด gate ที่ต้องอาศัย HIS จริง, IdP/PKI จริง, Acer hardware จริง หรือ clinical governance

## ผลการดำเนินงาน

| Workstream | ผลที่ตรวจสอบแล้ว | สถานะ gate |
|---|---|---|
| P0-001 HIS/Admission Gateway | Opaque tokenization, TTL expiry, revocation, outside admission idempotency, failure retention, mismatched Bundle acknowledgment rejection และ exact-scope purge ผ่านใน sandbox contract test | **In Progress** — hospital integration pending |
| P0-004 Recovery | Atomic checkpoint restart, stale temporary-file isolation, corrupt JSON fail-closed, unsupported/malformed payload handling, PII-bearing checkpoint rejection, sequence-inconsistency rejection และ SQLite WAL/synchronous-FULL reopen ผ่าน software fault harness | **In Progress** — physical power-loss/storage drill pending |
| Master regression | `run_all_tests.py` ผ่าน exit code `0`, รวม P0 contract/recovery tests ใหม่ | Software verification only |

## หลักฐานที่เพิ่ม

`his_admission_gateway_contract.py` เป็น test double สำหรับ outside boundary เท่านั้น โดยรับ raw HIS-looking reference แล้วทิ้งค่า raw หลังสร้าง opaque token. Hub-facing payload มีเฉพาะ `patient_token`, bed และ idempotency metadata. `test_p0_his_admission_contract.py` ขับผ่าน actual FastAPI boundary และตรวจว่า raw HN/AN ไม่อยู่ใน response หรือ audit output

`power_loss_recovery_harness.py` ใช้ fault injection แบบ deterministic กับ checkpoint file เพื่อทดสอบ committed restart, stale `.tmp` file, corrupt JSON, unsupported state version, malformed buffers, malformed sample metadata, PII-bearing checkpoint และ sequence inconsistency. `edge_runtime.py` ถูก harden ให้ restore fail-closed กับ payload/type ที่ไม่ถูกต้อง, PII keys, non-monotonic sample sequence และไม่รับ boolean เป็น sequence/drop counter โดย evidence ใหม่ระบุ `checkpoint_invariant_hardening=SOFTWARE_VERIFIED`

## สิ่งที่ยังไม่สามารถอ้างได้

Sandbox gateway ไม่ใช่ hospital token issuer, OIDC provider, mTLS client หรือ production identity authority. Sandbox recovery harness ไม่ใช่การตัดไฟจริง, disk-full drill, filesystem corruption บน Acer, storage-controller test, UPS/battery test หรือ OS/service recovery evidence

จึงยังห้ามใช้คำว่า **clinical-ready**, **tamper-proof**, **HIPAA/PDPA compliant 100%** หรือ **production-ready** จากผลชุดนี้ และยังไม่สามารถปิด P0-001/P0-004 ได้

## External gates ถัดไป

| Gate | สิ่งที่ต้องมี |
|---|---|
| Hospital HIS/Admission Gateway | FHIR version/profile, terminology, patient-reference policy, issuer, TTL/revocation, acknowledgment/error contract, idempotency behavior และ operator support decision |
| Real OIDC | Test tenant, issuer/JWKS, audience/algorithm, claim mapping, rotation, expiry/revocation transcript |
| Real mTLS | Test CA, client/server certificate chain, renewal, expiry/revocation และ network segmentation |
| Acer recovery/hardware | Deploy project บน Acer, controlled power cut, disk-full/corruption drill, reboot/service recovery, charger/battery/network/thermal evidence |
| Clinical validation | Shadow-mode protocol, human review, stop conditions, alarm-fatigue review และ clinical sign-off |

## Product positioning

จุดขายที่ควรรักษาคือ **Sovereign Edge / Offline-first**, **Zero-PII**, **Patient Safety Intelligence**, **Tamper-Evident Evidence**, **HIS/EMR Interoperability**, **Device Trust & Secure Provisioning**, **Outside-in Ward Workflow** และ **Sovereign Ward Operating Layer** โดยสื่อสารตาม evidence boundary ว่าเป็น **pilot-ready foundation** ไม่ใช่การรับรอง clinical หรือ production readiness
