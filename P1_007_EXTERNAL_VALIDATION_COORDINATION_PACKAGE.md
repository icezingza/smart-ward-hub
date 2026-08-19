# P1-007 — External Validation Coordination & Pilot Readiness Package

**สถานะ:** Software coordination contract ผ่าน; external validation และ clinical authorization ยังไม่เริ่ม

## วัตถุประสงค์

P1-007 เป็นชุดประสานงานหลักฐานสำหรับส่งต่อให้เจ้าของระบบโรงพยาบาล, security reviewer, reliability operator และ clinical governance โดยไม่ได้ทำหน้าที่อนุมัติการทดสอบกับผู้ป่วยจริง ชุดนี้ช่วยให้ทุก external gate มี owner, evidence requirement, status และ blocker ที่ตรวจสอบย้อนกลับได้

## Gate inventory

| Gate | Domain | Owner role | Evidence ที่ต้องได้รับจริง | สถานะเริ่มต้น |
|---|---|---|---|---|
| GV-01 | Clinical governance | clinical owner | approved protocol, consent/waiver, signed scope | OPEN |
| GV-02 | Privacy/security | privacy/security reviewer | Zero-PII review, retention decision, access-control review | OPEN |
| GV-03 | HIS/admission | integration owner | real HIS transcript, FHIR reconciliation, failure recovery | OPEN |
| GV-04 | Identity/transport | security owner | real OIDC validation, mTLS handshake, key-rotation transcript | OPEN |
| GV-05 | Fixed Hub host | host operator | Acer hardening, firewall/ACL, service recovery | OPEN |
| GV-06 | Hardware/recovery | reliability owner | Serial S-001–S-015, power-loss drill, disk-full drill | OPEN |
| GV-07 | Forensic anchor | forensic owner | independent WORM receipt, trusted timestamp, cross-boundary verification | OPEN |
| GV-08 | Device Trust | security owner | manufacturer provenance, hardware key custody, revocation distribution | OPEN |
| GV-09 | Clinical operations | ward manager | staff training, manual fallback SOP, alarm-fatigue review | OPEN |
| GV-10 | Independent review | independent reviewer | analysis plan, adjudication plan, audit export | OPEN |

## Evidence workflow

Evidence references must be bounded, traceable identifiers and must not contain raw HN, AN, MRN or National ID markers. A gate can receive software or simulation evidence as `EVIDENCE_SUBMITTED`, but that status does not mean external acceptance. A physical, clinical or infrastructure gate can be explicitly marked `BLOCKED` with a reason; blockers must not be hidden by aggregate readiness scores.

The package prevents duplicate evidence references, rejects unsupported claims such as `CLINICAL_VALIDATED`, `PRODUCTION_READY` and `TAMPER_PROOF`, and permanently sets `real_world_authorization=False`. The correct readiness result is an evidence-coordination status, not a clinical approval.

## Current known blockers

The Acer Spin N17H2 has no enumerated serial port and no deployed project/loopback fixture. Real HIS and IdP/mTLS integrations are absent. The external anchor is a software adapter/stub rather than an independently administered WORM service. Manufacturer CA/HSM or secure-element evidence is not present. Clinical owner, signed protocol, consent/waiver, staff training, independent review and alarm-fatigue review are not yet approved.

## Decision boundary

The package can be used to prepare a controlled pilot review meeting and collect evidence. It cannot authorize real patient testing, treatment decisions, diagnostic claims, production deployment, regulatory compliance claims or closure of any external gate without the responsible external owner and auditable evidence.


## GV-10 independent-review handoff

The detailed independent-review input is defined in `GV10_INDEPENDENT_REVIEW_DOSSIER.md` and checked by `GV10_SUBMISSION_CHECKLIST.md`. The software validator in `gv10_evidence.py` requires a bounded evidence reference, gate ID, SHA-256, timezone-aware collection timestamp, prepared-by role, redaction pass and chain-of-custody reference. Its output is always `INDEPENDENT_REVIEW_INPUT_UNVERIFIED`; it cannot authorize clinical validation or production use.
