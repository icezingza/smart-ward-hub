# Smart Ward Hub — P1-004 External Forensic Anchor Handoff

**วันที่:** 20 สิงหาคม 2026 (GMT+7)

## สรุปสถานะ

P1-004 มี **software adapter contract และ fault-injection baseline ผ่าน** แต่ยังไม่ปิดเป็น external validation. ระบบยังมีสถานะ **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation**, **pilot deployment configuration pending** และ **clinical validation pending**

## Key-custody test review

การตรวจ `test_key_custody_contract.py` พบว่า test เดิมครอบคลุม provisioning state, dual-control, software-fixture labeling, rotation, terminal revocation, lost-device transition และ private-material snapshot boundary ได้ดี แต่เดิมยังขาด negative cases สำหรับ blank identifiers, malformed fingerprints, duplicate key IDs, private-key argument, empty attestation ID, hardware fail-closed mode, duplicate approvers, blank reasons และ cross-device rotation

จึงเพิ่ม `P1_003_KEY_CUSTODY_TEST_REVIEW.md`, harden implementation ให้ตรวจ evidence ID และ trimmed identifiers และเพิ่ม `test_key_custody_contract_negative.py`. ผลเพิ่มเติมผ่านครบ โดยยังคงแยกชัดเจนว่า hardware-backed attestation เป็นเพียง fixture ใน software contract

## P1-004 anchor results

| Test area | Result |
|---|---|
| Receipt provider/package/hash identity | Passed |
| Stable idempotency replay | Passed; duplicate publish ไม่สร้าง record ใหม่ |
| Append-only delete refusal | Passed |
| Tampered provider record | Verification failed as expected |
| Invalid package/hash/configuration | Fail-closed |
| Mismatched provider/status/idempotency/hash/evidence/type receipt | Rejected before success |
| Zero-PII/private-key snapshot boundary | Passed |
| Full master regression | Exit code `0` |

`MemoryAppendOnlyAnchor` เป็น provider stub สำหรับ deterministic testing เท่านั้น และ receipt ใช้ evidence class `EXTERNAL_PROVIDER_RECEIPT_UNVERIFIED`. Local `FileAnchorStore` ยังคงเป็น `local_append_only_adapter`; ทั้งสองประเภทห้ามสื่อสารว่าเป็น tamper-proof หรือ external WORM

## External gates ที่ยังเปิด

P1-004 จะปิดได้ต่อเมื่อมี independently administered append-only/WORM service, authenticated transport, provider identity, trusted timestamp, retention/legal hold policy, access control, monitoring, retry/outage contract, independent receipt verification และ cross-boundary forensic chain verification. ต้องมี key custody และ operational owner ที่อนุมัติร่วมด้วย

ผลของเฟสนี้จึงเป็น **functional verification passed for the software adapter boundary**, ไม่ใช่หลักฐานของ external immutability, regulatory compliance, clinical readiness หรือ production deployment
