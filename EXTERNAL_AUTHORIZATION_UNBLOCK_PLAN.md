# External Authorization Unblock Plan — Smart Ward Hub

**Current state:** `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`

**Current gate matrix:** 7 `BLOCKED`, 3 `OPEN`, 0 `EVIDENCE_SUBMITTED`, 0 `PASSED`

**Clinical validation authorized:** `false`

**Production authorized:** `false`

**Runtime authority:** `NONE`

> แผนนี้เป็น coordination plan สำหรับผู้มีอำนาจภายนอก ไม่ใช่คำสั่งให้เริ่มทดสอบจริงโดยอัตโนมัติ ทุกกิจกรรมที่แตะ HIS, IdP, hardware, WORM, key custody หรือ clinical operation ต้องมี owner และ explicit approval แยกจาก repository software

## 1. Authorization path

การปลดบล็อกควรดำเนินเป็นลำดับ 5 waves เพื่อไม่ให้เกิดการเปิด trust boundary ก่อนเวลา:

| Wave | เป้าหมาย | Gates | Exit evidence |
|---|---|---|---|
| Wave 0 — governance control plane | แต่งตั้ง owner, scope, reviewer, test window, rollback และ stop authority | GV-01/GV-10 coordination | signed scope, analysis plan, reviewer appointment, evidence register |
| Wave 1 — identity/device/hardware foundation | ยืนยัน identity transport, device provenance และ physical recovery | GV-04, GV-08, GV-06 | IdP/mTLS transcript, manufacturer/key-custody record, serial/power-loss/disk-full evidence |
| Wave 2 — integration and forensic boundary | ยืนยัน HIS exchange และ external forensic custody | GV-03, GV-07 | HIS transcript/reconciliation, WORM receipt/trusted timestamp/cross-boundary verification |
| Wave 3 — privacy/host/operations | ปิด operational prerequisites สำหรับ ward pilot | GV-02, GV-05, GV-09 | retention/access decision, Acer hardening evidence, training/manual fallback/alarm-fatigue review |
| Wave 4 — independent review decision | ตรวจ evidence ทั้งชุดและตัดสินใจ external authorization | GV-10 plus all gates | signed independent finding/decision with scope, expiry and rollback |

## 2. Detailed blocker worklist

| Gate | Priority | Owner role | Software baseline | Required external evidence | Dependencies | Stop condition |
|---|---:|---|---|---|---|---|
| GV-01 | P0 | `clinical_owner` | P1-006 readiness, shadow-mode contracts | approved protocol, consent/waiver, signed scope | reviewer appointment, clinical governance meeting | ห้าม clinical validation หรือ interventional activity ก่อนลงนาม |
| GV-04 | P0 | `security_owner` | OIDC/mTLS-ready code and launcher | real OIDC discovery/claims, real mTLS handshake, certificate/key rotation | IdP test tenant, certificate owner, isolated network | ห้ามใช้ real credentials หรือ production identity transport ก่อน transcript ผ่าน |
| GV-08 | P0 | `security_owner` | device trust/key custody software contracts | manufacturer provenance, hardware key custody, dual-control issuance, rotation, revocation distribution | OEM/manufacturer, custody owner, key ceremony | ห้าม bind real devices หรืออ้าง hardware root of trust จาก software tests |
| GV-06 | P0 | `reliability_owner` | Serial framing, bench runner, power-loss harness | COM enumeration, serial loopback S-015, power-loss drill, disk-full drill | Acer host, isolated fixture, operator phrase | ห้าม physical run หากไม่มี `I_HAVE_A_NONPRODUCTION_LOOPBACK` และ fixture isolation |
| GV-03 | P1 | `integration_owner` | HIS sandbox contract and structured FHIR acknowledgement | real HIS transcript, FHIR reconciliation, failure recovery | GV-04 identity boundary, integration test window | ห้ามต่อ real HIS หรือส่ง admission data ก่อน boundary/rollback approval |
| GV-07 | P1 | `forensic_owner` | external anchor adapter and local FileAnchorStore | independent WORM receipt, trusted timestamp, cross-boundary verify | external provider, retention owner, custody reference | ห้ามเรียก local hash/receipt ว่า external immutability หรือ tamper-proof |
| GV-09 | P1 | `ward_manager` | shadow-mode/runbook/manual fallback contracts | staff training, manual fallback SOP, alarm-fatigue review, escalation roster | GV-01 scope and clinical owner | ห้าม controlled pilot ก่อน staff competency และ manual fallback sign-off |

## 3. Open-gate closure track

External authorization ต้องปิด 3 gates ที่ปัจจุบัน `OPEN` ด้วย ไม่ใช่เฉพาะ 7 blockers:

| Gate | Owner | Required evidence | Closure rule |
|---|---|---|---|
| GV-02 | `privacy_security_reviewer` | zero-PII review, retention decision, access-control review | reviewer accepts evidence and records residual risk |
| GV-05 | `host_operator` | Acer hardening checklist, firewall ACL, service recovery | target-host evidence is independently checked |
| GV-10 | `independent_reviewer` | analysis plan, adjudication plan, audit export | independent reviewer accepts/rejects with finding closure plan |

## 4. Evidence submission rules

ทุก evidence ใหม่ต้องผ่าน `gv10_evidence.py`, `controlled_pilot_operations.py` และ external validation gate contract ก่อนส่ง:

1. ใช้ evidence ID ใหม่และไม่ reuse ID เดิม
2. ระบุ gate ID, evidence class, SHA-256, timezone-aware timestamp, prepared-by role, redaction `PASS` และ chain-of-custody reference
3. สำหรับ gate ที่ `BLOCKED` ต้องเรียก `reopen(reason)` ก่อนจึง submit evidence ใหม่ได้
4. ห้ามส่ง raw HN/AN/MRN/National ID หรือ claim `clinical-ready`, `production-ready`, `tamper-proof`
5. แยก `SOFTWARE_VERIFIED`, `SIMULATION_ONLY`, `EXTERNAL_UNVERIFIED` และ `CLINICAL_GOVERNANCE_UNVERIFIED`
6. Local manifest/receipt เป็น tamper-evident coordination evidence เท่านั้น; external WORM, trusted timestamp และ cryptographic signature ต้องมีหลักฐานจาก trust boundary จริง

## 5. Decision gates and exit criteria

| Decision point | Required condition | Current result |
|---|---|---|
| Package integrity | Manifest/hash/redaction/provenance checks pass | Passed locally, 6/6 checks |
| External-review readiness | All required package fields and owners present | Coordination-ready only |
| Technical authorization | GV-02 through GV-08 evidence accepted | Not met |
| Clinical authorization | GV-01 and GV-09 governance sign-off | Not met |
| Independent review | GV-10 findings closed or accepted with residual risk | Not met |
| Controlled pilot go/no-go | External owner signed scope, expiry, rollback and stop authority | `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION` |

## 6. Recommended execution order

เริ่มจาก Wave 0 โดยไม่เปิด production network: แต่งตั้ง owner และ independent reviewer, freeze evidence manifest, approve test windows และ record stop authority จากนั้นทำ GV-04/GV-08/GV-06 เป็น technical foundation tracks แบบแยกสภาพแวดล้อม ต่อด้วย GV-03/GV-07 และปิด GV-02/GV-05/GV-09 เมื่อ governance พร้อม สุดท้ายส่ง package ให้ GV-10 adjudication และรอ external signed decision

## 7. Explicit non-authorization boundary

ซอฟต์แวร์ชุดนี้ไม่สามารถเปลี่ยนสถานะเป็น `AUTHORIZED_BY_EXTERNAL_OWNER`, ไม่สามารถตั้ง `clinical_validation_authorized=true`, ไม่สามารถตั้ง `production_authorized=true` และไม่สามารถให้ `runtime_authority` ได้จากผล test หรือ simulation เพียงอย่างเดียว
