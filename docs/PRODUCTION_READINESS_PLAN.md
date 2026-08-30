# Smart Ward Hub - Production Readiness Plan

สถานะเอกสาร: planning baseline
สถานะระบบปัจจุบัน: software baseline ผ่าน CI; production and clinical authorization ยังไม่ผ่าน

เอกสารนี้เป็นแผนงานสำหรับเตรียม production และ controlled pilot ไม่ใช่การอนุมัติให้ใช้กับผู้ป่วยจริง

## 1. หลักการตัดสินใจ

- ผล CI ยืนยันคุณภาพของ source และ software tests เท่านั้น
- Simulation ไม่ใช่หลักฐานจากอุปกรณ์, HIS, IdP, WORM หรือ clinical operation จริง
- ทุก gate ต้องมี owner, evidence, วันที่ตรวจ และ decision ที่ตรวจสอบย้อนหลังได้
- ห้ามตั้ง `clinical_validation_authorized=true`, `production_authorized=true` หรือ `runtime_authority` จาก local test
- หากพบความเสี่ยงที่ควบคุมไม่ได้ ให้หยุดการทดสอบและ rollback ทันที

## 2. ลำดับการทำงาน

| Phase | งานหลัก | ผลลัพธ์ที่ต้องเก็บ | สถานะ |
|---|---|---|---|
| 0. Governance | แต่งตั้ง product, clinical, security, integration, reliability และ quality owner | signed scope, reviewer, stop authority | BLOCKED |
| 1. Product boundary | ล็อก intended use, exclusions, user groups และ target countries | approved product boundary and regulatory classification | BLOCKED |
| 2. Safety and quality | ทำ risk file, hazard analysis, traceability และ change control | approved risk controls and requirements matrix | BLOCKED |
| 3. Technical validation | ทดสอบ hardware, power-loss, disk-full, backup/restore และ recovery | reproducible bench evidence | BLOCKED |
| 4. Security and integration | ทดสอบ OIDC, mTLS, key lifecycle, HIS/FHIR และ network boundary | external transcripts and reconciliation evidence | BLOCKED |
| 5. Human factors | ทดสอบ usability, alert workflow, training และ manual fallback | clinical usability and training records | BLOCKED |
| 6. Controlled pilot | เปิดเฉพาะ scope, site, window และ operator ที่อนุมัติ | pilot log, incidents, metrics and stop decisions | NOT_STARTED |
| 7. Production release | independent review, release approval, rollback rehearsal และ support handoff | signed go/no-go and versioned release record | BLOCKED |

## 3. Production gate checklist

ก่อนเปิดใช้งานจริง ทุกข้อด้านล่างต้องเป็น `PASS` หรือมี exception ที่ผู้มีอำนาจลงนาม พร้อมวันหมดอายุ, containment และ stop authority:

- [ ] Intended use และ regulatory classification ผ่านการ review
- [ ] Quality process, document control, CAPA และ change control ใช้งานจริง
- [ ] Risk management file และ residual-risk acceptance ได้รับอนุมัติ
- [ ] Requirements-to-test traceability ครบทุก safety requirement
- [ ] Versioned artifact, SBOM, dependency audit และ release notes ครบ
- [ ] Hardware/device identity, serial/BLE และ power-loss evidence ผ่าน
- [ ] OIDC/mTLS, certificate rotation และ revocation evidence ผ่าน
- [ ] HIS/FHIR sandbox reconciliation และ failure recovery ผ่าน
- [ ] Backup, restore, disaster recovery และ rollback rehearsal ผ่าน
- [ ] Threat model, security assessment, vulnerability response และ incident plan ผ่าน
- [ ] Usability, alert-fatigue, training และ manual fallback review ผ่าน
- [ ] Privacy/legal review และ data retention/access decision ผ่าน
- [ ] Named production owner, clinical owner, on-call และ support contact ครบ
- [ ] Independent reviewer ลงนาม go/no-go

## 4. Evidence record format

ทุก evidence ใหม่ต้องมีอย่างน้อย:

```text
evidence_id
gate_id
evidence_class
artifact_sha256
collected_at_utc
prepared_by_role
independent_verification_required
redaction_status
chain_of_custody_ref
source_revision
scope_and_expiry
```

ใช้ evidence class แยกให้ชัดเจน:

- `SOFTWARE_VERIFIED`
- `SIMULATION_ONLY`
- `EXTERNAL_UNVERIFIED`
- `CLINICAL_GOVERNANCE_UNVERIFIED`
- `BLOCKER_RECORD`

ห้ามใช้ raw patient identifiers, secrets หรือ private keys ใน evidence package

## 5. Immediate next actions

1. แต่งตั้ง owner และ independent reviewer
2. อนุมัติ intended use, scope, test window, rollback และ stop conditions
3. สร้าง risk file และ traceability matrix จาก requirements ที่มีอยู่
4. จัด isolated hardware/HIS/IdP test environments โดยไม่ใช้ข้อมูลผู้ป่วยจริง
5. เก็บ external evidence ตาม gate ID แล้วส่งให้ reviewer ตรวจ
6. เปิด controlled pilot เฉพาะเมื่อทุก blocker มีหลักฐานหรือ approved exception
7. สร้าง production release หลัง signed go/no-go เท่านั้น

## 6. Current decision

จากหลักฐานใน repository ปัจจุบัน:

```text
software_ci: PASS
software_evidence: READY_FOR_EXTERNAL_REVIEW
external_authorization: NOT_GRANTED
clinical_validation_authorized: false
production_authorized: false
runtime_authority: NONE
pilot_gate_status: BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
```

รายละเอียด blocker และ owner อยู่ใน [PILOT_READINESS_CHECKLIST.md](PILOT_READINESS_CHECKLIST.md), [CONTROLLED_PILOT_BLOCKER_ANALYSIS.md](../CONTROLLED_PILOT_BLOCKER_ANALYSIS.md) และ [EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md](../EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md)
