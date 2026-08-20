## Cover

**Smart Ward Hub**

**Controlled-Pilot Operations: Blocker Analysis & External Authorization Plan**

รายงาน software/evidence coordination — 20 สิงหาคม 2026

## Slide 1 — ข้อสรุปสำหรับผู้ตัดสินใจ

- สถานะ operations: `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`
- 10 gates: 7 `BLOCKED`, 3 `OPEN`, 0 submitted/passed
- Clinical validation / production authorization: `false`; runtime authority: `NONE`
- การทดสอบ software และ manifest integrity ผ่าน แต่ยังไม่ใช่ external approval

## Slide 2 — ผลตรวจ evidence package

- Manifest integrity checks ผ่าน 6/6: schema, manifest hash, receipt binding, non-PII refs
- มี 4 artifact entries พร้อม SHA-256, timestamp, prepared-by role, redaction `PASS`
- Receipt เป็น `SIGNED_STYLE_SIMULATION_NOT_CRYPTOGRAPHIC_SIGNATURE`
- แปลผล: tamper-evident coordination evidence; ไม่ใช่ WORM, trusted timestamp หรือ external custody

## Slide 3 — สถานะ 10 External Gates

- BLOCKED: GV-01, GV-03, GV-04, GV-06, GV-07, GV-08, GV-09
- OPEN: GV-02 Privacy/Security, GV-05 Host Hardening, GV-10 Independent Review
- ไม่มี gate ใดเป็น `EVIDENCE_SUBMITTED` หรือ `PASSED`
- Gate ที่ BLOCKED ต้อง `reopen(reason)` ก่อน submit evidence ใหม่

## Slide 4 — 7 Blockers ที่ยังปิด External Authorization

- P0 / Critical: GV-01 Clinical Governance, GV-04 Identity Transport, GV-08 Device Trust & Key Custody
- P0 / High: GV-06 Physical Recovery Bench
- P1 / High: GV-03 HIS Integration, GV-07 External WORM Anchor, GV-09 Clinical Operations
- ทุก blocker มี software reference แต่ external evidence ยัง `NOT_VERIFIED`

## Slide 5 — P0 Foundation: Governance, Identity, Device, Hardware

- GV-01: clinical owner/committee ต้องลงนาม protocol, scope และ consent/waiver decision
- GV-04: ทดสอบ IdP จริง, OIDC claim, mTLS handshake, certificate/key rotation
- GV-08: manufacturer provenance, hardware custody, issuance/rotation/revocation evidence
- GV-06: fixture non-production, COM enumeration, serial/power-loss/disk-full drills

## Slide 6 — P1 Boundary: HIS, Forensics, Ward Operations

- GV-03: HIS transcript, FHIR acknowledgement/reconciliation, failure recovery
- GV-07: independent WORM receipt, trusted timestamp, cross-boundary readback
- GV-09: training, manual fallback SOP, alarm-fatigue review, escalation roster
- ห้ามเริ่ม external integration หรือ ward pilot หากไม่มี owner, isolated scope และ stop/rollback condition

## Slide 7 — แผน 5 Waves เพื่อปลดบล็อก

- Wave 0: appoint owners/reviewer, signed scope, test window, stop authority
- Wave 1: GV-04 + GV-08 + GV-06 technical foundation
- Wave 2: GV-03 + GV-07 integration/forensics
- Wave 3: GV-02 + GV-05 + GV-09 privacy/host/operations
- Wave 4: GV-10 independent adjudication และ external signed decision

## Slide 8 — หลักฐานที่ต้องส่งและกติกา transition

- Evidence ใหม่ต้องมี gate ID, SHA-256, timezone timestamp, redaction `PASS`, chain-of-custody, prepared-by role
- ต้องแยก SOFTWARE_VERIFIED / SIMULATION_ONLY / EXTERNAL_UNVERIFIED / CLINICAL_GOVERNANCE_UNVERIFIED
- Blocked gate ต้อง reopen ด้วยเหตุผลก่อน submission
- ห้าม raw HN/AN/MRN, forbidden claims และการใช้ local receipt เป็น external authorization

## Slide 9 — Decision Criteria & Stop Conditions

- Local package integrity: ผ่าน 6/6 แต่ยังเป็น software check
- Technical authorization: GV-02 ถึง GV-08 ต้องมี external evidence accepted
- Clinical authorization: GV-01 และ GV-09 sign-off
- Independent review: GV-10 findings closed/accepted
- Controlled-pilot go/no-go: external owner ลงนาม scope, expiry, rollback และ stop authority

## Slide 10 — ข้อเสนอการดำเนินการถัดไป

- อนุมัติ Wave 0: แต่งตั้ง owner, independent reviewer และ freeze evidence register
- ขอ environment ที่แยกจาก production สำหรับ IdP/HIS/serial loopback/WORM verification
- เลือก schedule สำหรับ physical Acer bench ตาม phrase `I_HAVE_A_NONPRODUCTION_LOOPBACK`
- คงสถานะ controlled production prototype; clinical validation pending
