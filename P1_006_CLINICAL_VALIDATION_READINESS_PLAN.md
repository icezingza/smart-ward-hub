# P1-006 — Clinical Validation Readiness Plan

**สถานะ:** Software preflight contract เริ่มแล้ว; **ยังไม่พร้อมสำหรับการทดสอบกับผู้ป่วยจริง**

## วัตถุประสงค์

P1-006 ไม่ใช่การอนุมัติ clinical validation และไม่ใช่การสร้างผลลัพธ์ทางการแพทย์ แต่เป็นการเตรียมหลักฐานและตรวจว่าทีมมี protocol, owner, safety controls, privacy controls, fallback และ analysis plan ครบพอที่จะส่งให้ clinical governance พิจารณา

## ขั้นตอนการเตรียมความพร้อม

| Stage | ขั้นตอน | ผลผลิตที่ต้องมี | Gate owner |
|---|---|---|---|
| 1 | Define intended use | ระบุ decision-support scope, excluded use, ward/device scope และ population ที่จะศึกษา | Clinical owner |
| 2 | Approve protocol | protocol version, inclusion/exclusion criteria, endpoints, review rubric และ analysis plan | Clinical governance |
| 3 | Privacy and security | token issuance/mapping custody, Zero-PII export review, retention, access control, auth/mTLS และ audit plan | Privacy/security reviewer |
| 4 | Operational safety | stop conditions, incident response, escalation contact, manual fallback, rollback และ backup/restore drill | Technical + ward owner |
| 5 | Device/system qualification | device inventory, serial/network qualification, clock/freshness, host hardening, HIS acknowledgment และ recovery evidence | Reliability/integration owner |
| 6 | Human factors | training, ward walkthrough, alert wording, acknowledgement workflow, alarm-fatigue review และ no-treatment-order interpretation | Clinical + ward owner |
| 7 | Governance approval | signed approval ID, approved window, scope, data retention, named reviewers and change-control authority | Clinical governance |
| 8 | Controlled shadow run | non-interventional run, daily review, incident log, data-quality review and stop/resume decisions | Named operating team |
| 9 | Independent review | reconcile raw observation with shadow records, review missed/indeterminate/device-fault cases and audit completeness | Independent reviewer |
| 10 | Decision gate | continue, modify, pause or reject; no automatic move to treatment workflow | Governance board |

## ข้อกำหนดต้องผ่านก่อนเริ่มทดสอบจริง

ต้องมี clinical owner และ technical owner ที่ระบุชื่อ, protocol ที่อนุมัติ, intended/excluded use, inclusion/exclusion criteria, privacy/security review, consent หรือ waiver ที่ได้รับอนุมัติ, data-retention decision, staff training, stop conditions, incident response, rollback plan, manual fallback, backup/restore evidence, device qualification, auth/transport validation, HIS integration evidence, independent review plan และ analysis plan

นอกจากนี้ต้องมีการกำหนดว่า shadow signal ไม่ใช่ diagnosis, ไม่ใช่ treatment order และไม่แทนที่ vital-sign measurement หรือ clinical assessment ของโรงพยาบาล ระบบต้องเริ่มจาก non-interventional shadow mode โดยปิด workflow-changing notifications จนกว่าจะมีการอนุมัติแยกต่างหาก

## Hard stops

ห้ามเริ่ม real-world clinical validation หากขาด clinical governance approval, consent/waiver, stop/rollback path, manual fallback, privacy review, device qualification, unresolved critical security incident, raw identity leakage, data-retention decision หรือ independent review owner. การผ่าน software preflight ไม่ถือเป็น authorization

## P1-006 software evidence

`clinical_validation_readiness.py` ตรวจ completeness ของ gate และคืนสถานะ `NOT_READY_FOR_CLINICAL_VALIDATION` หรือ `READY_FOR_EXTERNAL_GOVERNANCE_REVIEW` เท่านั้น โดยบังคับ `real_world_authorization=False`, `clinical_approval_required=True` และ evidence class `SOFTWARE_PREFLIGHT_UNVERIFIED` เสมอ

ผล preflight จึงใช้สำหรับจัดเตรียมเอกสารและแสดงช่องว่างเท่านั้น ไม่สามารถใช้อนุมัติการทดลองกับผู้ป่วยจริง, อ้าง clinical accuracy, clinical safety effectiveness หรือ regulatory compliance ได้
