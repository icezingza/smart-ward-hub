# Smart Ward Hub — Residual-Risk Hardening Report

**สถานะระบบ:** P0-hardened software baseline; pilot deployment configuration pending  
**รูปแบบการส่งมอบ:** controlled production prototype with pilot-ready foundation  
**ข้อจำกัด:** clinical validation pending

## 1. บทสรุปผู้บริหาร

รอบนี้ได้ปิดช่องว่าง residual risk ที่สามารถควบคุมได้ภายในซอฟต์แวร์ของ Smart Ward Hub โดยเชื่อม `edge_controls.py` เข้ากับ FastAPI application จริง เพิ่ม process-local sliding-window rate limiting, structured audit events, request correlation ID, zero-PII redaction, handover sync idempotency และ local forensic anchor adapter. การเปลี่ยนแปลงถูกทดสอบด้วย regression module ใหม่และถูกรวมเข้า `run_all_tests.py`.

ผลที่รายงานนี้ยืนยันคือ **functional verification passed** ตามหลักฐานจาก software test suite. ไม่ควรสรุปเกินหลักฐานว่าเป็น clinical-ready, tamper-proof, HIPAA/PDPA compliant 100% หรือ production-ready. โดยเฉพาะ OIDC/mTLS กับ IdP จริง, hardware/network, clinical validation, external forensic anchoring, key custody, host hardening, power-loss testing และ real HIS integration ยังคงเป็น external validation gates.

## 2. ขอบเขตการเปลี่ยนแปลง

| พื้นที่ | สิ่งที่เพิ่มหรือเปลี่ยน | สถานะตามหลักฐาน |
|---|---|---|
| Rate limiting | Middleware ใช้ `SlidingWindowRateLimiter`, keyed ด้วย client host, ตอบ `429` พร้อม `Retry-After` และบันทึก denied event | Implemented, process-local |
| Request identity | `X-Request-ID` ถูกสร้างหากไม่มี header และถูก propagate ใน response กับ audit record | Implemented baseline |
| Replay protection | Telemetry ใช้ per-device monotonic `sequence`; duplicate/out-of-order packet ถูกปฏิเสธด้วย `409` | Implemented software control |
| Handover idempotency | `HandoverRecord.synced` เป็น durable gate, `SyncAttempt` เก็บ attempt และ lock ป้องกัน concurrent double-purge | Implemented for single-process Edge owner model |
| Structured audit | JSONL event schema มี version, event type, outcome, request ID, timestamp, actor, resource และ details | Implemented local baseline |
| Zero-PII audit | `patient_token`, `patient_id`, `name`, HN และ sensitive keys ถูก redact recursively; actor subject ถูก hash แบบสั้นเพื่อ correlation | Implemented baseline |
| Forensic anchor | หลัง freeze package ระบบเขียน `block_hash`, `chain_tip` และ package ID ไปยัง local append-only JSONL adapter เมื่อ configure path | Experimental/local adapter |
| Documentation | อัปเดต `SECURITY_BASELINE.md`, `RISK_REGISTER.md`, `.env.example` และรายงานฉบับนี้ | Completed |

## 3. หลักฐานจากการทดสอบ

### 3.1 Residual-control regression

`test_residual_controls.py` ผ่านทุกกรณี ได้แก่ direct sliding-window enforcement, HTTP middleware rate-limit response, monotonic sequence replay rejection, handover sync ซ้ำโดยไม่ purge ซ้ำ, forensic chain verification, local anchor output, structured audit JSONL และตรวจว่า audit log ไม่มี demo patient token แบบ raw.

ผลสำคัญของ idempotency test คือ request แรกที่ได้รับ acknowledgment จะ purge aggregate ตาม contract ส่วน request ซ้ำจะตอบ `ACKNOWLEDGED_IDEMPOTENT` และคืนจำนวนเดิมโดยไม่ทำ destructive purge รอบที่สอง. หลักฐานนี้เป็น software behavior ภายใต้ single-process Edge owner model เท่านั้น.

### 3.2 Full regression suite

คำสั่ง `python3 run_all_tests.py` ผ่านครบทุกรายการ รวม functional levels 1–6, security baseline, authentication fail-closed, bounded edge runtime, P0 hardening, residual controls, Device Trust enforce/observe regression, session workflow regression, Outside-in admission regression, Roaming Tablet synchronization regression, migration validation, reliability validation และ pilot simulation. Master runner ระบุแยกไว้แล้วว่า Phase 6 เป็น software simulation ไม่ใช่ clinical หรือ hardware validation.

### 3.3 Software reliability validation

| รายการ | ผลที่วัดได้ | การตีความที่ถูกต้อง |
|---|---:|---|
| Simulated devices | 30 | software harness |
| Concurrent requests | 600 | software concurrency test |
| All status 200 | true | application-level acceptance |
| p50 latency | 227.988 ms | measured in sandbox run |
| p95 latency | 690.216 ms | measured in sandbox run |
| p99 latency | 926.509 ms | measured in sandbox run |
| Maximum latency | 1215.514 ms | measured in sandbox run |
| Duplicate sequence | passed | replay control evidence |
| Unpaired device | passed | authorization/state guard evidence |
| Untrusted Host | passed | host-header control evidence |
| Checkpoint recovery | passed | process-boundary simulation |

ค่าข้างต้นเป็น **software simulation/verification** ไม่ใช่ SLA และไม่ใช่ผล network, hardware, battery หรือ clinical measurement. รายละเอียดเต็มอยู่ใน `reliability_validation_result.json`.

### 3.4 30-day pilot simulation

| รายการ | ผลที่วัดได้ | ขอบเขต |
|---|---:|---|
| Simulated duration | 30 days | generated software workload |
| Simulated devices | 30 | concurrent application exercise |
| Daily packets accepted | 900 | simulated telemetry only |
| Concurrent ingestion | 175.730 ms | 30 requests in software harness |
| Clinical validation | not performed | external gate |
| Hardware/battery validation | not performed | external gate |
| External network sync validation | not performed | external gate |

ผลนี้ยืนยันความต่อเนื่องของ software workflow ภายใต้ simulation แต่ไม่สามารถยืนยัน sensitivity, specificity, alarm fatigue, battery life, packet loss, RF behavior, power-loss behavior หรือ HIS delivery ได้.

## 4. การแยกความหมายของ forensic evidence

`SHA-256` hash chain และ local anchor file ให้หลักฐานแบบ **tamper-evident** ภายในขอบเขตที่ไฟล์และ runtime ยังอยู่ภายใต้ trust boundary เดียวกัน. Local anchor adapter ไม่ใช่ independent WORM storage, ไม่ใช่ blockchain, ไม่ใช่ external timestamp authority และไม่ทำให้ private key custody เกิดขึ้นโดยอัตโนมัติ.

> ข้อกำหนดการสื่อสาร: ใช้คำว่า “tamper-evident evidence” หรือ “local append-only anchor adapter” เท่านั้น และห้ามใช้คำว่า “tamper-proof” จากผลทดสอบชุดนี้.

ก่อนใช้ forensic output เป็น evidence ข้ามองค์กร ต้องเปลี่ยนหรือ mirror adapter ไปยัง independently administered append-only/WORM service พร้อมกำหนด key custody, trusted time, retention, access control, verification drill และ incident procedure.

## 5. Residual risks ที่ยังต้องปิดด้วย external validation

| Risk | ทำไมยังไม่ปิด | Acceptance gate ที่ต้องทำ |
|---|---|---|
| OIDC กับ IdP จริง | โค้ด verifier พร้อม แต่ยังไม่มี real issuer/JWKS/revocation/clock evidence | ทดสอบ token lifecycle, rotation, failure modes และ audit กับ IdP โรงพยาบาล |
| mTLS และ certificate lifecycle | launcher fail-closed และพร้อม config แต่ยังไม่มี certificate/CA/network evidence | ทดสอบ mutual trust, rotation, revocation, firewall และ segmentation |
| Hardware/network | software harness ไม่จำลอง RF, battery, disk, power transient หรือ packet-loss pattern ได้ครบ | hardware-in-loop, soak, reconnect, power-loss, disk-full และ network fault tests |
| Clinical validation | triage เป็น decision-support prototype ไม่ใช่ diagnosis | approved clinical protocol, ground truth, performance metrics, alarm fatigue review และ sign-off |
| External forensic anchoring | local file ยังอยู่ใน trust boundary เดียว | external WORM/append-only, independent administration, key custody และ restore/verify drill |
| Key custody | ยังไม่มี HSM/secret manager integration | rotation, revocation, dual control และ access evidence |
| Host hardening | application controls ไม่ครอบคลุม OS และ physical host | OS benchmark, patching, least privilege, disk encryption, firewall, monitoring, backup/restore |
| Real HIS/EMR | FHIR shape ถูกตรวจเชิง functional แต่ยังไม่ผ่าน endpoint จริง | contract test, timeout/retry, reconciliation, duplicate delivery และ safe purge |

## 6. ข้อเสนอแนะก่อน pilot deployment

ให้คงสถานะ deployment เป็น **pilot deployment configuration pending** จนกว่า operator จะทำ migration ด้วย Alembic, ตั้งค่า OIDC และ mTLS ด้วยค่าจริง, แยก filesystem สำหรับ database/checkpoint/audit/anchor, ตั้ง backup และ restore drill, calibrate rate limits, ทบทวน runbook กับ ward staff และเปิด clinical shadow mode โดยมี stop conditions.

ในระยะ pilot ควรใช้ service topology แบบ single Edge owner ต่อ ward ตามสมมติฐานปัจจุบัน และห้าม scale เป็นหลาย process หรือหลาย node โดยไม่ออกแบบ coordinated rate limiting, shared state, distributed idempotency และ consistent audit delivery เพิ่มเติม.

## 7. ไฟล์ที่เกี่ยวข้อง

| ไฟล์ | หน้าที่ |
|---|---|
| `edge_controls.py` | Rate limiter, audit sink, redaction, request ID และ local anchor adapter |
| `main.py` | Middleware และ endpoint integration |
| `test_residual_controls.py` | Residual-control regression test |
| `device_trust.py` | Canonical Ed25519 signed-telemetry verification |
| `test_device_trust.py` | Enforce-mode enrollment, mutation, replay and revocation tests |
| `test_device_trust_observe.py` | Observe-mode continuity test |
| `WARD_WORKFLOW_CONTRACT.md` | Admission, NFC, session, reset, hot-swap and forensic contract |
| `OUTSIDE_IN_WARD_WORKFLOW.md` | Outside console, non-PII bed availability and tokenized admission contract |
| `test_outside_admission.py` | Bed availability, reservation, expiry, idempotency and pairing commit tests |
| `alembic/versions/6a7b8c9d0e11_outside_admission.py` | Outside admission availability migration |
| `ROAMING_TABLET_ARCHITECTURE.md` | Fixed Hub plus Roaming Tablet synchronization contract |
| `ROAMING_TABLET_BASELINE_REPORT.md` | Roaming implementation evidence and validation gates |
| `test_roaming.py` | Snapshot cursor, stale revision, command idempotency and reset safety tests |
| `alembic/versions/7b8c9d0e1f22_roaming_commands.py` | Roaming command and alert acknowledgement migration |
| `test_session_workflows.py` | Ward workflow regression test |
| `alembic/versions/4f1a2c7d8e90_workflow_sessions.py` | Workflow persistence migration |
| `SECURITY_BASELINE.md` | Baseline control matrix และ validation boundaries |
| `RISK_REGISTER.md` | Risk ownership, status และ next gates |
| `.env.example` | Runtime configuration template |
| `reliability_validation_result.json` | Software reliability evidence |
| `pilot_simulation_result.json` | Software-only 30-day simulation evidence |

## References

[1]: ./test_residual_controls.py "Residual-control regression test"
[2]: ./reliability_validation_result.json "Software reliability validation result"
[3]: ./pilot_simulation_result.json "30-day software pilot simulation result"
[4]: ./SECURITY_BASELINE.md "Security baseline"
[5]: ./RISK_REGISTER.md "Risk register"
[6]: ./DEVICE_TRUST_BASELINE_REPORT.md "Device Trust baseline report"
[7]: ./WARD_WORKFLOW_CONTRACT.md "Ward workflow contract"


## 8. Strategic product differentiator record

The project now records **Device Trust & Secure Provisioning Layer** and **Outside-in Ward Workflow** as strategic differentiators and roadmap capability in `PRODUCT_DIFFERENTIATORS.md`. The intended value proposition is a controlled device-to-evidence trust chain built on manufacturer-authenticated identity, canonical telemetry, replay-aware ingestion, Zero-PII Edge processing, frozen forensic packages and external append-only anchoring.

The current release does not implement or claim all of those future capabilities. The software baseline now also includes Outside-in bed availability/admission preparation and Fixed Hub plus Roaming Tablet snapshot/command synchronization. The software baseline now includes Ed25519 public-key enrollment, canonical signed telemetry verification in enforce mode, and basic credential lifecycle controls. Asymmetric manufacturer CA provisioning, secure-element/HSM key custody, safe geofence trust degradation and external WORM anchoring remain planned or externally validated. The approved claims therefore remain **Sovereign Edge**, **Zero-PII by design**, **Patient Safety Intelligence**, **Tamper-Evident Evidence**, **HIS/EMR Interoperability**, and **Device Trust with hardware, manufacturer and clinical validation pending**.
