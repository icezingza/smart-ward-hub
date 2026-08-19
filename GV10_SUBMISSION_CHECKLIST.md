# GV-10 — Independent Review Submission Checklist

## A. Package governance

- [ ] กำหนด `dossier_id`, review scope และ intended use อย่างชัดเจน
- [ ] แต่งตั้งผู้เตรียมหลักฐานและผู้ตรวจสอบอิสระคนละบทบาทกัน
- [ ] ระบุว่า package เป็น `INDEPENDENT_REVIEW_INPUT_UNVERIFIED`
- [ ] ยืนยันว่า `clinical_validation_authorized=false` และ `production_authorized=false`
- [ ] บันทึกวันที่และ timezone ของการ freeze package

## B. Artifact integrity

- [ ] สร้าง manifest ชื่อไฟล์, size, SHA-256 และ source commit ของทุก artifact
- [ ] คำนวณ hash ก่อนส่งและตรวจซ้ำหลัง copy/transfer
- [ ] ใช้ `evidence_id` ที่ไม่ซ้ำและผูกกับ gate ID
- [ ] บันทึก `chain_of_custody_ref` สำหรับทุก entry
- [ ] ใช้ timestamp แบบ timezone-aware
- [ ] หาก artifact เปลี่ยน ต้องสร้าง evidence ID และ hash ใหม่ ห้ามเขียนทับหลักฐานเดิม

## C. Privacy and redaction

- [ ] ตรวจไม่ให้ artifact reference มี HN, AN, MRN หรือ National ID
- [ ] ตรวจว่าไม่มี `.env`, private key, mTLS key, credential, patient mapping หรือ raw clinical payload
- [ ] ตรวจ audit/log export ให้ redact แล้ว และบันทึก `redaction_status=PASS`
- [ ] ตรวจ screenshots, crash dumps, network traces และ backup exports แยกจาก source/test evidence
- [ ] ส่งข้อมูล sensitive ผ่าน secure channel ที่องค์กรอนุมัติเท่านั้น

## D. Reproducibility

- [ ] ระบุ command ที่ใช้ทดสอบและผล exit code
- [ ] ระบุ Python/package/runtime version ที่จำเป็น
- [ ] ให้ผู้ตรวจทำซ้ำ deterministic tests ได้โดยไม่ต้องใช้ patient data
- [ ] แยก software test, deterministic simulation, external-unverified และ clinical-governance-unverified อย่างชัดเจน
- [ ] แนบ negative/fail-closed test result ไม่ใช่เฉพาะ happy path

## E. Ten-gate traceability

- [ ] GV-01 มี protocol, consent/waiver และ signed scope หรือบันทึก blocker
- [ ] GV-02 มี Zero-PII, retention และ access-control review หรือบันทึก blocker
- [ ] GV-03 มี real HIS/FHIR transcript หรือบันทึกว่าเป็น sandbox contract เท่านั้น
- [ ] GV-04 มี real OIDC/mTLS/key rotation transcript หรือบันทึก blocker
- [ ] GV-05 มี Acer host-hardening, firewall/ACL และ service-recovery evidence หรือบันทึก blocker
- [ ] GV-06 มี S-001–S-015, power-loss และ disk-full evidence หรือบันทึก blocker
- [ ] GV-07 มี independent WORM receipt, trusted timestamp และ cross-boundary verification หรือบันทึก blocker
- [ ] GV-08 มี manufacturer provenance, hardware custody และ revocation distribution หรือบันทึก blocker
- [ ] GV-09 มี training, manual fallback SOP และ alarm-fatigue review หรือบันทึก blocker
- [ ] GV-10 มี analysis plan, adjudication plan และ audit export

## F. Independent-review outcome

- [ ] ผู้ตรวจยืนยันว่า artifact ตรงกับ manifest/hash
- [ ] ผู้ตรวจทำซ้ำ test commands ที่ระบุและบันทึกผลแยกจากผู้เตรียม
- [ ] ผู้ตรวจตรวจ claim boundary และ prohibited wording
- [ ] ผู้ตรวจแยก findings เป็น accepted-for-review, clarification, blocked-external-evidence หรือ rejected
- [ ] ทุก finding มี severity, owner, evidence reference และ due action
- [ ] ไม่มีการเปลี่ยนสถานะเป็น clinical validated หรือ production ready จาก package นี้เพียงอย่างเดียว
