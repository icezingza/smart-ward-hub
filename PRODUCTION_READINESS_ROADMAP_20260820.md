# Smart Ward Hub — Production-Readiness Roadmap

**วันที่จัดทำ:** 2026-08-20  
**ขอบเขต:** เปลี่ยนจาก `NOT_PRODUCTION_READY` ไปสู่การอนุมัติใช้งานจริงโดยมีหลักฐานจาก software, external infrastructure, hardware, clinical governance และ independent review ครบถ้วน  
**สถานะปัจจุบัน:** `NOT_PRODUCTION_READY`

> เอกสารนี้เป็น roadmap และ gate contract ไม่ใช่ production authorization. Local software, deterministic simulation หรือ master regression ไม่สามารถตั้ง `production_authorized=true` หรือเปลี่ยน External Gate เป็น `PASSED` ได้

## 1. Decision baseline

Production-readiness audit ล่าสุดระบุ `external_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false`, `runtime_authority=NONE` และ `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`. Classification คือ Implemented 5, Experimental 1, Unverified 6 และ Planned 1. หลักฐานอ้างอิงคือ [`PRODUCTION_READINESS_EVIDENCE_AUDIT.md`](./PRODUCTION_READINESS_EVIDENCE_AUDIT.md) sections Decision summary และ Evidence audit matrix.

External Gate matrix ปัจจุบันมี 7 `BLOCKED`, 3 `OPEN`, 0 `EVIDENCE_SUBMITTED` และ 0 `PASSED`. ดังนั้นงานที่ต้องทำไม่ใช่เพียงเพิ่ม feature แต่ต้องสร้างและให้ผู้มีอำนาจภายนอกยอมรับหลักฐานจริงใน trust boundary ที่ถูกต้อง.

## 2. Definition of Production Ready

ให้ใช้ claim `Production Ready` ได้ก็ต่อเมื่อเงื่อนไขทั้งหมดต่อไปนี้เป็นจริงและมี signed decision จากผู้มีอำนาจภายนอก:

| เงื่อนไข | เกณฑ์ผ่าน |
|---|---|
| Software release | version, source revision, migrations, configuration และ dependency manifest ถูก freeze; master regression ผ่าน; no critical unresolved software finding |
| Identity and transport | GV-04 ผ่านด้วย real OIDC/JWKS, claims/audience, mTLS handshake, certificate rotation/revocation และ network segmentation transcript |
| HIS/Admission | GV-03 ผ่านด้วย real non-production HIS/Gateway exchange, token boundary, acknowledgement, timeout/retry และ reconciliation evidence |
| Host and hardware | GV-05/GV-06 ผ่านบน Acer Spin N17H2 target host ด้วย host hardening, serial/USB/BLE/network, power-loss, disk-full, reboot/soak และ recovery transcript |
| Device trust and custody | GV-08 ผ่านด้วย manufacturer provenance, key issuance, dual control, rotation, revocation และ lost-device drill |
| Forensic boundary | GV-07 ผ่านด้วย independent append-only/WORM receipt, trusted time, retention, key custody และ independent read-back |
| Clinical governance | GV-01/GV-09 ผ่านด้วย approved protocol, clinical owner, consent/waiver decision, shadow-mode results, human-factors/alarm-fatigue review, training และ manual fallback |
| Privacy/security | GV-02 ผ่านด้วย zero-PII review, retention/access decision, secret handling, audit review และ residual-risk acceptance |
| Independent review | GV-10 ผ่านด้วย complete evidence package, findings closure/acceptance, scope, expiry, rollback และ signed independent decision |
| Operations | Backup/restore, monitoring, incident response, stop authority, rollback version, RPO/RTO และ service recovery ผ่านบน target environment |

ถ้าเงื่อนไขใดไม่ผ่าน สถานะต้องคง `NOT_PRODUCTION_READY` หรือ `BLOCKED`; ห้ามใช้ผลของ gate อื่นมาชดเชย gate ที่ไม่ผ่าน.

## 3. Execution sequence

### Wave 0 — Governance control plane

**เป้าหมาย:** แต่งตั้งคนและขอบเขตก่อนแตะระบบจริง. ต้องมี `clinical_owner`, `security_owner`, `integration_owner`, `reliability_owner`, `forensic_owner`, `ward_manager`, `host_operator`, `independent_reviewer` และ `stop_authority` ตามหน้าที่ที่แยกกัน.

**Entry criteria:** software baseline และ dossier schema ถูก freeze; มี release candidate hash; มี test inventory; ไม่มี raw HN/AN/MRN/National ID ใน evidence package.

**Evidence ที่ต้องมี:** signed scope, approved test window, named roles, stop criteria, rollback plan, custody plan, independent-verification plan, manifest SHA-256, timezone-aware timestamps และ evidence register.

**Exit criteria:** Wave 0 governance package ได้รับการลงนามโดย owner ที่มีอำนาจจริง; independent reviewer และ stop authority ถูกแต่งตั้ง; test window/rollback/expiry ชัดเจน. สถานะนี้ยังไม่ใช่ authorization และยังไม่เปิด production network.

**Stop conditions:** owner ไม่ครบ, role ซ้ำกันจนขาด separation of duties, scope ไม่ลงนาม, rollback ไม่ทดสอบ, evidence chain ไม่สมบูรณ์ หรือมีคำขอให้ตั้ง authorization flag จาก local code.

### Wave 1 — Identity, device trust และ hardware foundation

#### GV-04: Real OIDC/mTLS identity transport — Owner: `security_owner`

**Entry criteria:** มี isolated non-production IdP/HIS tenant, certificate owner, test identities, approved network path และ test window จาก Wave 0.

**Evidence:** discovery/JWKS response hash, issuer/audience/claim validation, access-token expiry/revocation, mTLS handshake, server/client certificate chain, rotation, revocation, clock/skew และ network ACL transcript. Secrets ต้องถูก redacted และไม่เก็บ private key ใน evidence bundle.

**Exit:** reviewer ตรวจ transcript แล้วรับรอง identity, transport, rotation และ revocation ครบ. Static bearer token ใช้ได้เฉพาะ local bench/development ไม่ใช่ production evidence.

#### GV-08: Device Trust and key custody — Owner: `security_owner`

**Entry criteria:** มี manufacturer/OEM identity model, approved custody owner, key ceremony และ device inventory.

**Evidence:** device provenance, issuance/attestation record, dual-control key ceremony, key ID mapping, rotation/revocation distribution, lost-device disablement และ custody read-back.

**Exit:** real device identity และ key lifecycle ถูกยืนยันจาก owner/custodian; ห้ามเรียก local Device Trust simulation ว่า hardware root of trust.

#### GV-06: Acer/serial/power-loss bench — Owner: `reliability_owner`

**Entry criteria:** Acer Spin N17H2 ถูกแยกเป็น non-production fixture; operator มีวลี `I_HAVE_A_NONPRODUCTION_LOOPBACK`; มี backup/rollback point และ stop authority.

**Evidence:** COM enumeration result, serial loopback/framing/partial-read transcript, USB/NFC/BLE/network adapter inventory, power interruption, reboot, disk-full, WAL recovery, checkpoint recovery, charger/battery/sleep behavior, thermal/soak และ service restart.

**Exit:** ทุก S-series bench cases ผ่านหรือมี signed external residual-risk decision; หากไม่มี COM port ที่ enumerate ต้องคง GV-06 `BLOCKED` และไม่อ้าง hardware validation.

### Wave 2 — HIS integration และ external forensic boundary

#### GV-03: Real HIS/Admission Gateway — Owner: `integration_owner`

**Entry criteria:** GV-04 transport ผ่าน, HIS sandbox owner ลงนาม, admission/token contract freeze, rollback และ data-minimization review ผ่าน.

**Evidence:** admission request/response transcript ที่ redacted, token-to-encounter mapping, acknowledgement/reconciliation, duplicate/idempotency, timeout/retry, rejected/malformed input, outage/manual fallback และ post-test cleanup. Raw HN/PII ต้องไม่เข้า Edge evidence.

**Exit:** integration reviewer รับรองว่า raw identity ถูกหยุดที่ Admission Gateway, Hub รับเฉพาะ approved token boundary, และ failure ไม่ทำให้ pairing/telemetry state เสียหาย.

#### GV-07: Independent forensic anchoring — Owner: `forensic_owner`

**Entry criteria:** มี external append-only/WORM service, retention owner, trusted time source, key custodian และ independent read-back channel.

**Evidence:** anchor submission, external receipt, trusted timestamp, package hash/signature, read-back from independent channel, retention/immutability policy, key rotation/revocation และ failure/duplicate/replay drill.

**Exit:** external reviewer ตรวจสอบ cross-boundary read-back ได้. Local FileAnchorStore และ hash chain เป็นเพียง tamper-evident software baseline ไม่ใช่ WORM หรือ tamper-proof.

### Wave 3 — Privacy, host hardening และ clinical operations

#### GV-02: Privacy/security review — Owner: `privacy_security_reviewer`

**Evidence:** zero-PII data-flow review, retention schedule, access-control/RBAC review, secret-source review, screen/privacy/site review, audit redaction/size policy, incident response และ accepted residual-risk register.

#### GV-05: Acer host hardening — Owner: `host_operator`

**Evidence:** dedicated non-admin service identity, source/runtime separation, encrypted volume, firewall export/approved port scan, docs disabled, loopback binding or approved gateway, OIDC/mTLS config, time sync, patch inventory, auto-start/restart/rollback, encrypted backup, physical power behavior, privacy/kiosk controls และ monitoring.

**Mandatory stop conditions:** runtime path อยู่ใน source tree, docs เปิด, bind non-loopback โดยไม่มี approved gateway, static credentials ฝังใน script, DB อยู่บน volume ที่ไม่เข้ารหัส, backup restore ไม่ได้ หรือ operator ระบุ rollback version ไม่ได้. เกณฑ์นี้อ้างอิง [`P1_HOST_HARDENING_CHECKLIST.md`](./P1_HOST_HARDENING_CHECKLIST.md).

#### GV-09: Clinical operations — Owner: `ward_manager`

**Evidence:** staff training/competency, manual fallback SOP, alarm escalation roster, alarm-fatigue review, RESET_PENDING workflow review, outside-in admission/walk-round walkthrough, downtime drill, incident/stop workflow และ sign-off จาก clinical owner.

**Exit:** clinical staff สามารถทำงานต่อได้เมื่อ Hub/เครือข่าย/อุปกรณ์/identity ใช้งานไม่ได้ และมี stop authority ที่ปฏิบัติได้จริง.

#### GV-01: Clinical governance — Owner: `clinical_owner`

**Evidence:** approved clinical protocol, intended-use boundary, patient safety hazard analysis, consent/waiver decision, inclusion/exclusion criteria, clinical validation/shadow-mode plan, safety thresholds, human-factors review, adverse-event/escalation plan และ committee decision.

**Exit:** clinical committee/ผู้มีอำนาจอนุมัติ scope และ clinical validation plan เป็นลายลักษณ์อักษร. ห้ามใช้คำว่า clinical-ready หรืออ้าง accuracy จาก software simulation ก่อน gate นี้ผ่าน.

### Wave 4 — Independent review and authorization decision

**Owner:** `independent_reviewer` พร้อม external authority ที่มีอำนาจตัดสินใจ.

**Evidence package:** ทุก evidence ต้องมี evidence ID ใหม่, gate ID, evidence class, SHA-256, timezone-aware timestamp, `prepared_by_role`, `redaction=PASS`, chain-of-custody, source revision, test-run/case ID และ independent read-back. Wave E bundle ต้องมี exactly one record ต่อ T-01–T-12 และคง no-authorization boundary.

**Review steps:** ตรวจ manifest/hash → ตรวจ source revision → ตรวจ evidence class → ตรวจ gate coverage → ตรวจ failed/blocked cases → ตรวจ residual risks → ตรวจ scope/expiry/rollback → ออก signed finding/decision.

**Exit:** GV-10 reviewer ลงนามว่า gates ผ่านหรือมี residual risk ที่ยอมรับได้โดยผู้มีอำนาจ, ระบุ scope/expiry/rollback/stop authority และตัดสินใจ external authorization อย่างชัดเจน. Local simulator ห้ามสร้าง decision นี้แทน.

## 4. Backup, monitoring และ rollback readiness

### Backup/restore gate

ต้องใช้ SQLite backup API ไม่ใช่ copy `.db` ขณะ WAL active; ต้องตรวจ `PRAGMA integrity_check`, สร้าง manifest ที่มี source revision/size/SHA-256/timestamp, กำหนด retention/destination/access control และทำ isolated restore ด้วยวลี `I_UNDERSTAND_RESTORE_TO_NONPRODUCTION_TARGET`. ต้องมี RPO/RTO ที่ owner อนุมัติและ transcript ของ post-restore checks: schema/migration, pairing, alerts, pending sync, forensic manifest, ownership และ readiness ก่อน resume telemetry. อ้างอิง [`BACKUP_RESTORE_CONTRACT.md`](./BACKUP_RESTORE_CONTRACT.md).

### Minimum operational monitoring

ก่อน pilot/production ต้องมีหลักฐานว่า monitor ตรวจ service health/readiness, disk headroom, SQLite/WAL/checkpoint state, audit-chain integrity, backup freshness, sync backlog, device connectivity, authentication/authorization failures, certificate expiry, rate-limit rejection, telemetry sequence gaps, alert lifecycle และ manual fallback status. ทุก alert ต้องมี owner, severity, timestamp, correlation ID และ stop/escalation rule. ยังไม่ควรถือว่ามี `/metrics` หรือ monitoring production เพียงเพราะมีชื่อ endpointในเอกสาร ต้องมี scrape/alert transcript จริง.

### Rollback/stop triggers

ให้หยุดหรือ rollback ทันทีเมื่อพบ identity/claim mismatch, expired/revoked certificate, untrusted response, raw PII leak, audit integrity failure, duplicate/out-of-order telemetry ที่ recover ไม่ได้, WAL/disk-full/storage integrity failure, backup freshness breach, failed restore, service version ไม่ตรง manifest, alert delivery gap, clinical stop request, staff manual-fallback failure, device key compromise หรือ external owner ถอน scope/หมดอายุ.

Rollback ต้องระบุ version/hash ที่จะกลับ, ผู้อนุมัติ, target state, data reconciliation, evidence capture และ post-rollback health check. ห้าม resume telemetry จนกว่า pairing/alerts/pending sync/forensic/schema/ownership/readiness checks ผ่าน.

## 5. Readiness ladder และ claim transition

| Level | สถานะ | สิ่งที่พูดได้ |
|---:|---|---|
| 0 | `NOT_PRODUCTION_READY` — ปัจจุบัน | controlled production prototype; P0-hardened software baseline; functional verification passed; pilot-ready foundation; clinical validation pending |
| 1 | `READY_FOR_EXTERNAL_OWNER_APPOINTMENT` | Wave E coordination package พร้อมให้แต่งตั้ง owner; external execution ยังไม่เริ่ม |
| 2 | `PILOT_DEPLOYMENT_CONFIGURATION_PREPARED` | target-host preflight ผ่านใน environment ที่อนุมัติ; physical/clinical gates ยัง pending |
| 3 | `TECHNICAL_GATES_ACCEPTED` | GV-02 ถึง GV-08 ผ่านตาม external review; ยังห้าม claim clinical/production หาก GV-01/GV-09/GV-10 ไม่ผ่าน |
| 4 | `CLINICAL_AND_OPERATIONAL_GATES_ACCEPTED` | protocol, shadow-mode, training, manual fallback และ human-factors ผ่าน; ยังต้อง independent decision |
| 5 | `EXTERNAL_AUTHORIZATION_GRANTED` | external authority ลงนาม scope/expiry/rollback/stop authority; ยังต้อง release go/no-go บน target environment |
| 6 | `PRODUCTION_RELEASE_CANDIDATE` | release artifact, host, backup/restore, monitoring, rollback และ operational rehearsal ผ่านสำหรับ version เดียวกัน |
| 7 | `PRODUCTION_READY` | external authorization และ all required gates accepted; claim ใช้ได้เฉพาะ scope/version/expiry ที่ลงนาม และต้องมี post-go-live monitoring |

ระบบควรถือ level เป็น evidence/status ที่มี owner และ expiry ไม่ใช่ boolean ที่ local code ตั้งเอง. การเปลี่ยนจาก level 0 ไป level 7 ต้องเป็น external decision record ที่ตรวจสอบย้อนกลับได้.

## 6. Immediate next actions

1. แต่งตั้ง Wave 0 owners, independent reviewer และ stop authority; ลงนาม scope/test window/rollback/expiry.
2. Freeze release candidate: source commit, dependency manifest, config template, schema/migration revision, evidence manifest และ forbidden-claim register.
3. เปิด technical tracks แบบแยก environment: GV-04 OIDC/mTLS, GV-08 key custody และ GV-06 Acer/serial/power-loss; ยังไม่เชื่อม production credentials หรือ production HIS.
4. หลัง technical prerequisites ผ่าน ให้ทำ GV-03 HIS sandbox และ GV-07 external WORM/anchor.
5. ปิด GV-02/GV-05/GV-09 ด้วย privacy, Acer host, training/manual fallback และ clinical operations evidence.
6. ทำ GV-01 clinical committee decision และ clinical shadow-mode ตาม protocol; ห้ามทดสอบเชิง clinical ก่อนมี approval.
7. ส่ง complete package ให้ GV-10 independent review; แก้ findings/reopen blocked gates ตาม contract และรอ signed decision.
8. ทำ production release rehearsal บน exact version/host/config ที่จะใช้จริง พร้อม backup restore, monitoring, incident, stop และ rollback drill.
9. ออก go/no-go record โดย external authority; ถ้า gate ใดไม่ผ่านให้คง `NOT_PRODUCTION_READY`.
10. หลัง go-live ทำ daily evidence/monitoring review, backup freshness, certificate/key expiry, incident review, access review และ scheduled revalidation ตาม scope/expiry.

## 7. Final non-authorization boundary

จนกว่าจะมี external signed decision และหลักฐานครบตาม roadmap นี้ ให้คงค่า `external_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false`, `runtime_authority=NONE` และ `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.

ห้ามใช้คำว่า `clinical-ready`, `tamper-proof`, `HIPAA/PDPA compliant 100%` หรือ `production-ready` จาก functional tests, deterministic simulation, local hash chain, local backup restore หรือ documentation เพียงอย่างเดียว.

## References

[1]: ./PRODUCTION_READINESS_EVIDENCE_AUDIT.md "Production-readiness evidence audit"
[2]: ./EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md "External Authorization Unblock Plan"
[3]: ./NEXT_PHASE_PRIORITY_MATRIX.md "Next Phase Priority Matrix"
[4]: ./P1_HOST_HARDENING_CHECKLIST.md "Acer Host Hardening Checklist"
[5]: ./BACKUP_RESTORE_CONTRACT.md "Backup/Restore Contract"
[6]: ./WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md "Wave 0 Governance Review Checklist"
