# Smart Ward Hub — สรุปสถานะ P1-001 ถึง P1-006

## Slide 1 — หน้าปก: Smart Ward Hub P1 Milestones

**Sovereign Ward Operating Layer — P1 Operational Trunk & Governance Baseline**

สรุปสถานะความคืบหน้าการยกระดับระบบปฏิบัติการประจำวอร์ด ตั้งแต่งานสำรองข้อมูล ความปลอดภัยโฮสต์ การจัดการกุญแจอุปกรณ์ การประทับหลักฐานทางนิติวิทยาศาสตร์ ไปจนถึงกรอบธรรมาภิบาลทางคลินิก

**สถานะทางการ:** `controlled production prototype` · `P0-hardened software baseline` · `functional verification passed` · `pilot-ready foundation` · `clinical validation pending`

แหล่งอ้างอิง: `README.md`, `tasks.md`, `SMART_WARD_HANDOFF_STATUS.md`

## Slide 2 — ภาพรวม P1 Roadmap: สร้างลำต้นของระบบ

ภาพรวมของ 6 งานสำคัญใน Phase 1 (Operational Deployment Trunk):

- **P1-001:** Backup & Restore (SQLite Backup API, Manifest Checksum, Isolated Restore)
- **P1-002:** Host Hardening (Readiness Validator, Windows Acer Auto-Run, Least Privilege)
- **P1-003:** Device Trust Key Custody (Dual Control, Key Rotation, Terminal Revocation)
- **P1-004:** Forensic Anchor Adapter (Receipt Identity, Idempotency, WORM Boundary)
- **P1-005:** Clinical Shadow-Mode (Safe Labels, Zero-PII Token, Non-Accuracy Metrics)
- **P1-006:** Clinical Validation Readiness (Preflight Gate, Prerequisite Checklist, Stop Conditions)

## Slide 3 — P1-001 & P1-002: การกู้คืนข้อมูลและความพร้อมของ Host

**P1-001 Backup/Restore:**
- ใช้งาน SQLite Backup API โดยตรง ปลอดภัยต่อ WAL Mode ไม่ใช้วิธี Copy ไฟล์เดี่ยว
- สร้าง Manifest พร้อม SHA-256 Checksum ตรวจจับการแก้ไขไฟล์สำรอง
- ระบบ Restore บน Isolated Target ป้องกันการเขียนทับ Database หลักโดยไม่ตั้งใจ
- ปฏิเสธไฟล์ Credential / Private Key ไม่ให้ปะปนใน Backup

**P1-002 Host Hardening & Acer Auto-Run:**
- ตัวตรวจความพร้อม `deployment_readiness.py` บังคับ Loopback Binding และ Pilot Defaults
- PowerShell/CMD Script สำหรับ Acer Spin N17H2 Auto-Run โดยไม่เก็บรหัสผ่านในสคริปต์

## Slide 4 — P1-003: Device Trust & Key Custody Lifecycle

- **Provisioning Identity:** ผูก `device_id` กับ Ed25519 Public Key Fingerprint
- **Dual-Control Activation:** บังคับผู้อนุมัติอย่างน้อย 2 คน พร้อมบันทึก Attestation Metadata
- **Key Rotation Linkage:** เชื่อมโยง `previous_key_id` และเปลี่ยนสถานะกุญแจเดิมเป็น `SUSPENDED` อัตโนมัติ
- **Terminal Revocation:** สถานะ `REVOKED` และ `LOST` เป็นสถานะสิ้นสุด ไม่สามารถเปิดใช้งานใหม่ได้
- **Private Key Boundary:** ห้ามนำ Private Key เข้าสู่ Registry หรือบันทึกใน Snapshot

## Slide 5 — P1-004: Forensic Anchor & FileAnchorStore Hardening

**FileAnchorStore (Local Baseline):**
- ตรวจสอบ Input Hash / Package ID อย่างเข้มงวด
- บังคับเก็บไฟล์นอก Source Tree เมื่อกำหนด `source_root`
- เพิ่ม Record Hash, Local Receipt และ Readback Verification ที่คัดกรองข้อมูลถูกแก้ไขออก

**External Anchor Adapter (P1-004 Contract):**
- ตรวจสอบความสอดคล้องของ Provider ID, Package ID, Block Hash และ Chain Tip
- Idempotency ป้องกันการสร้าง Anchor ซ้ำเมื่อมีการส่งซ้ำ
- ปฏิเสธคำสั่งลบข้อมูล (Append-Only Enforced)
- ปฏิเสธ Receipt กลายพันธุ์ใน Fault Injection Matrix

## Slide 6 — P1-005: Clinical Shadow-Mode & Zero-PII Boundary

**Zero-PII Token Boundary:**
- รับเฉพาะ Opaque Token ปฏิเสธรหัสตรงอย่าง `HN`, `AN`, `MRN`, `NATIONAL_ID`
- กรองคำระบุตัวตนใน `alert_id`, `device_id`, `bed_no` และ `context` (จำกัด 512 ตัวอักษร)

**Safe Signal Labels:**
- ใช้เฉพาะ `suspected fall`, `vital anomaly signal`, `device/perimeter warning`
- ห้ามใช้คำวินิจฉัย เช่น `diagnosis`, `sepsis`, `heart attack` หรือคำสั่งรักษา

**Stop & Resume Controls:**
- หยุดรับสัญญาณทันทีเมื่อเกิดเหตุ Privacy Leak, Alert Flood หรือ Sequence Corruption
- การกลับมาเปิดใหม่ต้องมี Approval ID ที่ได้รับอนุมัติอย่างเป็นทางการ

## Slide 7 — P1-005: การรายงานผลด้วย Non-Accuracy Metrics

คำเตือนสำคัญ: ตัวเลขจาก Shadow Mode **ไม่ใช่ Clinical Accuracy, Sensitivity หรือ Specificity**

| เมตริกที่ถูกต้อง | ความหมายทางปฏิบัติ | ข้อจำกัดและข้อควรระวัง |
|---|---|---|
| `signal_count` | จำนวน Signal ทั้งหมดที่ระบบสร้าง | นับเฉพาะข้อมูลในระดับซอฟต์แวร์ |
| `reviewed_count` | จำนวนเหตุการณ์ที่ผู้เชี่ยวชาญทบทวนแล้ว | ต้องรายงานคู่กับ Coverage เสมอ |
| `review_coverage` | สัดส่วนการทบทวน (`reviewed / total`) | หากต่ำเกินไปจะไม่สามารถสรุปแนวโน้มได้ |
| `unreviewed_signal_count` | จำนวนเหตุการณ์ที่ยังค้างการทบทวน | แสดงภาระงานที่ยังไม่เสร็จสิ้น |
| `confirmed_event_rate_over_reviewed` | สัดส่วนที่ Reviewer ระบุว่าตรงกับเหตุการณ์จริง | ไม่ใช่ค่าความไว (Sensitivity/PPV) |
| `false_positive_review_rate_over_reviewed` | สัดส่วนที่ Reviewer ระบุว่าไม่พบเหตุการณ์ | ใช้ดู Alarm Burden ไม่ใช่ความแม่นยำรวม |
| `mean_data_freshness_seconds` | ความล่าช้าของข้อมูลจากอุปกรณ์สู่ Hub | แสดง Network/Queue Latency |

## Slide 8 — P1-006: Clinical Validation Readiness Preflight

`clinical_validation_readiness.py` เป็นด่านตรวจ Software Preflight ที่ประเมิน 17 ข้อกำหนดก่อนขออนุมัติ:

- **Intended / Excluded Uses:** กำหนดขอบเขตการใช้งานเพื่อสนับสนุนการตัดสินใจอย่างชัดเจน
- **Governance Prerequisites:** Clinical Owner, Protocol Version, Inclusion/Exclusion Criteria
- **Safety & Privacy:** Privacy Review, Security Review, Consent/Waiver, Retention Decision
- **Operational Resilience:** Stop Conditions, Incident Response, Rollback Plan, Manual Fallback
- **System Qualification:** Backup Verified, Device Qualified, Auth/mTLS Ready, HIS Integrated

ผลลัพธ์ Preflight จะคืนเฉพาะ `READY_FOR_EXTERNAL_GOVERNANCE_REVIEW` หรือ `NOT_READY_FOR_CLINICAL_VALIDATION` โดยไม่อนุญาตให้เริ่มทดสอบกับผู้ป่วยจริงโดยอัตโนมัติ

## Slide 9 — สรุปตารางสถานะ P1-001 ถึง P1-006

| รหัส | ขอบเขตงาน | ผลการทดสอบระดับซอฟต์แวร์ | สถานะ | สิ่งที่ต้องทำจริงภายนอก |
|---|---|---|---|---|
| **P1-001** | Backup / Restore | Backup API, Manifest, Isolated Restore ผ่าน | Dry-Run Complete | Encrypted Storage & Real Restore Drill |
| **P1-002** | Host Hardening | Readiness Validator & Win Script ผ่าน | In Progress | Acer Account, ACL, Firewall, OS Patch |
| **P1-003** | Key Custody | Dual-Control, Rotation, Lost-State ผ่าน | In Progress | Manufacturer CA & Hardware HSM |
| **P1-004** | Forensic Anchor | Local Hardened & External Adapter ผ่าน | In Progress | Independent WORM & Trusted Timestamp |
| **P1-005** | Shadow-Mode | Safe Labels, Zero-PII, Metrics ผ่าน | In Progress | Clinical Owner & Alarm Fatigue Review |
| **P1-006** | Validation Readiness | 17-Gate Preflight Validator ผ่าน | In Progress | Clinical Governance Protocol Sign-off |

## Slide 10 — ข้อกำหนดก่อนเริ่ม Clinical Validation และก้าวต่อไป

**ข้อกำหนดที่ต้องผ่านก่อนเริ่มทดสอบระบบจริง (Clinical Validation Hard Gates):**
1. **Clinical Governance Sign-off:** ได้รับอนุมัติ Protocol, Consent/Waiver และแต่งตั้ง Clinical Owner
2. **Real Infrastructure:** เชื่อมต่อ HIS จริง, OIDC/mTLS จริง และ External Anchor WORM จริง
3. **Physical Hardware Bench:** รัน Loopback บน Acer Spin N17H2 และผ่าน Power-Loss Drill
4. **Safety & Fallback SOP:** บุคลากรผ่านการอบรม เข้าใจว่าไม่ใช่คำสั่งรักษา และมีขั้นตอน Manual Fallback

**ก้าวถัดไปของทีมวิศวกรรม:**
สร้าง **External Validation Coordination & Pilot Readiness Package** เพื่อส่งมอบหลักฐานทางเทคนิคให้แก่คณะกรรมการโรงพยาบาลและทีมคลินิกอย่างเป็นทางการ
