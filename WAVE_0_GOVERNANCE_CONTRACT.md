# Wave 0 Governance Contract — Smart Ward Hub

**สถานะ:** software/evidence contract baseline; external appointment and authorization pending
**วัตถุประสงค์:** เตรียม control plane สำหรับการขอ External Authorization โดยไม่สร้างสิทธิ์อนุมัติจากซอฟต์แวร์

> Wave 0 เป็นการเตรียม governance evidence เท่านั้น ไม่ใช่ clinical approval, HIS/IdP approval, hardware approval, controlled-pilot authorization หรือ production authorization

## 1. Governance boundary

Wave 0 ต้องเสร็จก่อนเปิด test window ที่แตะระบบภายนอก, ฮาร์ดแวร์จริง, ข้อมูลผู้ป่วย, clinical operation, key ceremony, HIS, IdP/mTLS หรือ external forensic custody โดยซอฟต์แวร์ทำได้เพียงตรวจรูปแบบและความครบถ้วนของ governance record ใน repository; ไม่สามารถยืนยันตัวบุคคล ลายเซ็น อำนาจตามองค์กร หรือสิทธิ์ทางคลินิกแทนผู้อนุมัติภายนอกได้

สถานะสูงสุดที่ local contract สร้างได้คือ `GOVERNANCE_PACKAGE_READY_FOR_EXTERNAL_REVIEW` และสถานะที่ยังต้องคงไว้ใน baseline คือ:

| Field | Required value |
|---|---|
| `clinical_validation_authorized` | `false` |
| `production_authorized` | `false` |
| `runtime_authority` | `NONE` |
| `external_authority` | `NONE` จนกว่าจะมีหลักฐานนอก trust boundary |
| `pilot_gate_status` | `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION` |

## 2. Required governance roles

ระบบต้องมี role appointment record สำหรับแต่ละบทบาท โดยใช้ `principal_ref` หรือ external directory reference แทนการฝังชื่อจริงลงใน software evidence:

| Role | Responsibility | Conflict rule |
|---|---|---|
| `clinical_owner` | รับรอง protocol scope, patient-safety boundary และ clinical stop criteria | ต้องแยกจาก system implementer |
| `privacy_security_reviewer` | ตรวจ Zero-PII, retention, access และ privacy/security residual risks | ต้องมีอำนาจ review แยกจากผู้พัฒนา |
| `security_owner` | รับผิดชอบ IdP/mTLS และ device-trust technical evidence | ห้ามเป็นผู้อนุมัติ clinical scope เพียงคนเดียว |
| `integration_owner` | รับผิดชอบ HIS/admission sandbox evidence และ rollback | ต้องมี HIS authority จากองค์กรจริง |
| `reliability_owner` | รับผิดชอบ Acer/serial/power-loss/disk-full bench evidence | ต้องยืนยัน physical fixture และ operator boundary |
| `forensic_owner` | รับผิดชอบ external WORM/timestamp/custody evidence | ต้องแยกจาก local artifact preparer เมื่อทำได้ |
| `ward_manager` | รับผิดชอบ training, manual fallback, escalation และ operational readiness | ต้องมี authority ของ ward จริง |
| `host_operator` | รับผิดชอบ fixed-host hardening และ recovery evidence | ต้องเข้าถึง target host อย่างได้รับอนุญาต |
| `independent_reviewer` | ตรวจ manifest, findings, analysis plan และ decision package | ต้องไม่มีส่วนได้เสียกับ implementation และต้องเป็น external appointee |
| `stop_authority` | สั่งหยุด test window เมื่อพบ safety, privacy, identity, hardware หรือ evidence breach | ต้องสามารถหยุดกิจกรรมได้โดยไม่รอผู้พัฒนา |
| `evidence_custodian` | ควบคุม manifest freeze, versioning, custody references และ export | ห้ามแก้ evidence หลัง freeze โดยไม่มี change record |

อย่างน้อยต้องมี `clinical_owner`, `independent_reviewer`, `stop_authority` และ `evidence_custodian` ที่มีสถานะ `APPOINTMENT_PENDING` หรือ `APPOINTED_EXTERNAL`; ถ้ายังไม่มี appointment จริง ห้ามเปลี่ยนเป็น governance-ready

## 3. Appointment record contract

ทุก appointment record ต้องมีอย่างน้อย:

| Field | Requirement |
|---|---|
| `appointment_id` | unique, immutable identifier |
| `role` | one of the approved governance roles |
| `principal_ref` | opaque external reference; ห้าม raw national ID/HN/AN/MRN |
| `organization_ref` | external organization reference ที่ตรวจสอบย้อนกลับได้ |
| `appointed_by_role` | ผู้มีอำนาจแต่งตั้งตาม governance policy |
| `scope` | responsibility และ decision boundary ของ role |
| `effective_from` / `expires_at` | timezone-aware timestamps |
| `conflict_declaration` | declared / reviewed / unresolved |
| `appointment_evidence_ref` | reference ไปยัง signed organizational record นอก software baseline |
| `verification_status` | `PENDING_EXTERNAL_VERIFICATION` หรือ `VERIFIED_OUTSIDE_BASELINE` |

Local validator ตรวจได้เพียง schema, timezone, uniqueness, role separation, expiry และ raw-identity boundary; ค่า `VERIFIED_OUTSIDE_BASELINE` ต้องมาจาก external evidence ไม่สามารถ self-declare จาก local test ได้

## 4. Signed scope contract

Signed scope ต้องระบุขอบเขตที่อนุญาตและห้ามทำอย่างชัดเจน:

| Field | Required content |
|---|---|
| `scope_id` | immutable scope identifier |
| `purpose` | วัตถุประสงค์ของ test/review เท่านั้น |
| `in_scope` | systems, devices, synthetic fixtures และ test endpoints ที่อนุญาต |
| `out_of_scope` | production network, real patient care, raw identifiers, unapproved HIS/IdP และ unapproved hardware |
| `environment` | isolated/sandbox/bench/ward และ network boundary |
| `test_window_ref` | link ไปยัง approved test window |
| `rollback_plan_ref` | reversible steps และ owner |
| `stop_criteria_ref` | triggers ที่ stop authority ใช้สั่งหยุด |
| `expiry` | timezone-aware expiry; ห้าม scope แบบไม่มีกำหนดหมดอายุ |
| `signed_by_external_role` | role ของผู้ลงนามภายนอก |
| `signature_ref` | external signature/custody reference; local simulation ห้ามตีความเป็น signature |
| `verification_status` | `PENDING_EXTERNAL_VERIFICATION` หรือ external verified |

Local package จะแสดง `scope_status=PENDING_EXTERNAL_SIGNATURE` จนกว่าจะมี external record จริง

## 5. Test-window contract

Test window ต้องจำกัดเวลา ระบบ และข้อมูลที่ใช้:

- `window_id`, `starts_at`, `ends_at` ต้องเป็น timezone-aware และ `ends_at` ต้องมากกว่า `starts_at`;
- ระบุ `allowed_systems`, `allowed_devices`, `allowed_networks`, `allowed_data_class` และ operator roles;
- default data class ต้องเป็น synthetic/non-PII; real patient data ต้องมี separate clinical governance record;
- ระบุ `preflight_checks`, `rollback_steps`, `stop_authority_ref`, `incident_channel_ref` และ `evidence_capture_plan`;
- ห้ามเปิด production network, real HIS, real IdP, external WORM หรือ clinical workflow หากไม่อยู่ใน signed scope และ test window ที่อนุมัติแล้ว;
- หลัง `ends_at` ห้ามรับ evidence ใหม่ภายใต้ window เดิม ต้องสร้าง window/version ใหม่

## 6. Stop-authority contract

Stop authority ต้องมี trigger ที่สั่งหยุดได้ทันทีโดยไม่ต้องรอการวิเคราะห์เพิ่มเติม:

| Trigger class | Examples |
|---|---|
| Safety | unexpected patient-facing behavior, alarm path failure, unsafe reset |
| Privacy | raw identity, PII leakage, unauthorized capture |
| Identity | real credential exposure, failed mTLS, unknown device trust |
| Infrastructure | power-loss corruption, disk-full, network boundary breach |
| Evidence | hash mismatch, missing custody, post-freeze mutation |
| Governance | expired scope, missing owner, untrained operator, unresolved conflict |

ทุก stop event ต้องมี `stop_event_id`, trigger class, detected_at, actor role, affected scope/window, immediate containment, notification ref และ restart approval ref. Local software ตรวจรูปแบบได้เท่านั้น; restart approval ต้องเป็น external decision

## 7. Evidence-register freeze

เมื่อ Wave 0 package พร้อมส่ง review ให้สร้าง immutable-style local freeze record:

| Field | Requirement |
|---|---|
| `freeze_id` | unique freeze identifier |
| `manifest_version` | version ที่ freeze |
| `manifest_sha256` | hash ของ manifest ที่ freeze |
| `previous_manifest_sha256` | hash ก่อนหน้าเมื่อมีการ chain |
| `frozen_at` | timezone-aware timestamp |
| `frozen_by_role` | `evidence_custodian` |
| `scope_id` / `window_id` | governance context |
| `change_policy` | append-only; edits require new version and reason |
| `custody_ref` | local simulation หรือ external custody reference ที่แยกชัดเจน |
| `external_verification_required` | `true` |
| `external_authority` | `NONE` ใน local baseline |

หลัง freeze ห้ามแก้ artifact ที่อ้างใน manifestแบบเงียบ ๆ หากมีการเปลี่ยนต้องสร้าง manifest version ใหม่, ระบุ reason, previous hash และ reviewer notification

## 8. State transitions

| State | Allowed transition | Meaning |
|---|---|---|
| `DRAFT` | `PENDING_APPOINTMENTS` | เริ่มกรอก governance package |
| `PENDING_APPOINTMENTS` | `PENDING_SCOPE_SIGNATURE` | appointment records มีครบตาม schema แต่ยัง external-unverified |
| `PENDING_SCOPE_SIGNATURE` | `PENDING_TEST_WINDOW_APPROVAL` | scope ถูกสร้างแต่ยังไม่ลงนามภายนอก |
| `PENDING_TEST_WINDOW_APPROVAL` | `READY_TO_FREEZE` | test window และ stop criteria ครบในรูปแบบ local |
| `READY_TO_FREEZE` | `FROZEN_LOCAL_PENDING_EXTERNAL_REVIEW` | manifest ถูก freeze ใน local baseline |
| `FROZEN_LOCAL_PENDING_EXTERNAL_REVIEW` | `GOVERNANCE_PACKAGE_READY_FOR_EXTERNAL_REVIEW` | local checks ผ่านและ package พร้อมส่ง reviewer |
| any active state | `BLOCKED` | missing/expired appointment, invalid scope, safety/privacy/evidence breach |
| `BLOCKED` | `REOPENED` | มี reason และ owner ใหม่ก่อนแก้ package |

ไม่มี transition จาก state ใดไป `AUTHORIZED_BY_EXTERNAL_OWNER`; สถานะนั้นอยู่ภายนอก software baseline

## 9. Acceptance criteria

1. Role appointment ทุก record มี unique ID, opaque principal reference, conflict status, expiry และ external appointment evidence reference.
2. Signed scope ระบุ in-scope, out-of-scope, environment, expiry, rollback, stop criteria และ external signature reference.
3. Test window จำกัดระบบ/ข้อมูล/เวลาและหมดอายุได้จริง.
4. Stop authority มี trigger, containment และ restart approval reference.
5. Evidence register freeze สร้าง deterministic manifest hash และบังคับ append-only versioning.
6. Missing external verification ทำให้สถานะคงเป็น `PENDING_EXTERNAL_VERIFICATION` หรือ `BLOCKED`.
7. Local software ไม่สามารถสร้าง clinical, production หรือ external authorization ได้.
