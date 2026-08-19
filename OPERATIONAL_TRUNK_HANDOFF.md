# Smart Ward Hub — Operational Trunk Handoff

**วันที่:** 20 สิงหาคม 2026 (GMT+7)

## สถานะ

Smart Ward Hub ผ่านการสร้างรากฐาน P0 และเริ่มสร้าง operational trunk แล้ว สถานะที่ถูกต้องคือ **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation**, **pilot deployment configuration pending** และ **clinical validation pending**

เฟสนี้เพิ่มชั้นที่ทำให้ระบบสามารถเตรียมตัวเข้าสู่ deployment ได้อย่างมีวินัยมากขึ้น ได้แก่ backup/restore contract, deployment readiness validator, Windows Acer auto-run template และ host-hardening checklist โดยทุกส่วนยังถูกติดป้ายตามหลักฐานจริงและไม่อ้างว่า Acer ถูก deploy หรือ hardened แล้ว

## ผลงานที่เสร็จ

| Capability | ผลการตรวจสอบ |
|---|---|
| SQLite backup | ใช้ SQLite backup API ไม่ copy `.db` เดี่ยวขณะ WAL active; ตรวจ integrity และสร้าง manifest |
| Restore | restore ไปยัง target แยก, verify SHA-256, atomic replacement และ exact non-production confirmation |
| Secret boundary | ปฏิเสธ artifact ที่มีชื่อ/นามสกุลคล้าย secret หรือ private key และไม่ bundle secret material |
| Readiness validation | ตรวจ pilot defaults, OIDC shape, loopback binding, non-wildcard hosts, runtime path separation และ Device Trust staging |
| Acer auto-run template | PowerShell/CMD wrapper พร้อม safe `-ValidateOnly`; bind service ที่ loopback และไม่ฝัง credentials |
| Host hardening | Checklist ครอบคลุม account, ACL, encryption, firewall, patching, time, service recovery, backup, privacy และ monitoring |
| Regression | Master suite ผ่าน exit code `0` รวม `test_backup_restore.py` และ `test_deployment_readiness.py` |

## หลักฐานและขอบเขต

`test_backup_restore.py` ผ่านการสร้าง SQLite backup bundle, manifest/checksum, isolated restore, refusal without exact confirmation, tamper detection และ secret-like artifact rejection. หลักฐานนี้เป็น software restore ไปยัง temporary target ไม่ใช่การกู้คืนจาก backup destination จริงหรือ encrypted Acer volume

`deployment_readiness.py` ผ่านทั้ง safe pilot configuration และ deliberate failure cases. Windows templates ใน `deploy/windows/` เป็น reference adaptation สำหรับ Acer Spin N17H2 และยังไม่รันบน Acer, ไม่สร้าง Windows account, ไม่ติดตั้ง Task Scheduler, ไม่ตั้งค่า Firewall, ไม่ลง certificate และไม่พิสูจน์ boot/service recovery

## ขั้นตอนเมื่อพร้อม deploy Acer

1. ติดตั้ง project และ Python environment บน Acer โดยใช้ source revision ที่อนุมัติ
2. สร้าง dedicated least-privilege account และ runtime/log directories นอก source tree
3. ตั้งค่า secret source สำหรับ OIDC/mTLS โดยไม่ใส่ token หรือ private key ใน repository หรือ scheduler arguments
4. รัน `deploy/windows/start_smart_ward_hub.ps1 -ValidateOnly`
5. ตรวจสอบ disk encryption, ACL, firewall, trusted time, backup destination และ rollback path
6. ค่อยลงทะเบียน Task Scheduler หรือ service wrapper ตาม host policy
7. รัน P0/P1 hardware checklist: boot, service restart, power interruption, disk-full, restore, network interruption, thermal, charger/battery และ kiosk recovery

## Gate ที่ยังเปิด

| Gate | สถานะ |
|---|---|
| Encrypted backup destination and retention approval | Pending |
| Real isolated restore on Acer | Unverified |
| Windows account/ACL/firewall/patch hardening | Unverified |
| Task Scheduler/service recovery on Acer | Unverified |
| OIDC/mTLS with hospital IdP/CA | Unverified |
| HIS/Admission Gateway real integration | Unverified |
| Physical serial/IoT bench | Not started |
| Power-loss/disk-full/filesystem drill | Unverified |
| Clinical shadow-mode and human-factors review | Pending |

## Claim boundary

ชั้น operational trunk ช่วยสนับสนุนคำอธิบายว่า **deployment configuration prepared** และ **software recovery/restore contract verified in isolation** เท่านั้น ห้ามใช้คำว่า **clinical-ready**, **tamper-proof**, **HIPAA/PDPA compliant 100%** หรือ **production-ready** จนกว่าจะมีหลักฐาน external validation ครบ
