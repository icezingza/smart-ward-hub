# P2-004 — Micro-RAG Registry / Rebuildable Index Hardening Plan

**สถานะก่อนเริ่ม:** `DocumentRegistry` และ `RebuildableIndexAdapter` มี software baseline ในหน่วยความจำ; model evaluation runner ยังดึง approved documents จาก `fixtures.json` โดยตรงและยังไม่ผูกกับ registry/index runtime

## Findings จาก baseline review

| Finding | ผลกระทบ | Acceptance criterion |
|---|---|---|
| Registry เป็น in-memory เท่านั้น | restart แล้ว lifecycle/manifest state หาย | เพิ่ม deterministic export/import แบบ JSON manifest + content payload โดยตรวจ hash และ schema ก่อนรับเข้า |
| Lifecycle transition ไม่เข้มงวด | state อาจเปลี่ยนย้อนกลับหรือข้ามขั้นโดยไม่มี policy | กำหนด transition matrix และ reject invalid transition; ทุก transition ต้องมี reason และ actor role |
| Expiry timestamp ไม่ได้บังคับ timezone | eligibility อาจตีความเวลาไม่ตรงกัน | validate ISO-8601 timezone-aware expiry/approval/revoke timestamps |
| Index snapshot ไม่สามารถ export/import | rebuild ซ้ำหลัง restart ทำไม่ได้และตรวจ provenance ไม่ครบ | เพิ่ม signed-by-manifest style snapshot hash, deterministic export/import และ verify registry manifest hash ก่อน query |
| Runner ใช้ fixture retrieval โดยตรง | runtime path ไม่เท่ากับ evaluated path | เพิ่ม registry-backed fixture loader / adapter boundary ก่อน rerun; รายงานต้องระบุ retrieval source |
| Adapter scope check พึ่ง retrieved set | evidence คนละ scope อาจถูก cite หาก upstream ส่งผิด | reject citation หาก `allowed_scope != expected_scope` และตรวจ `approved/current/non-PII` ซ้ำที่ adapter |
| Adapter support tokenization เป็น English-only | Thai evidence support อาจ false reject หรือรับไม่สม่ำเสมอ | เพิ่ม Thai bigram tokenization และ regression ทั้ง Thai-only / bilingual |
| Provider 429 ถูกนับปนกับ quality failure | score อาจถูกตีความผิด | แยก `MODEL_CALL_FAILED_PROVIDER_LIMIT`, `QUALITY_REJECTED` และ `PASSED`; บันทึก retry/HTTP summary แบบ redacted |

## สิ่งที่จะทำในเฟสนี้

1. เพิ่ม persistence contract ที่เป็น JSON-only, deterministic, no-secret และ atomic-write friendly โดยไม่ใช้ runtime database หรือ raw patient identity
2. เพิ่ม transition guard: `DRAFT → APPROVED → DEPRECATED/REVOKED` และ `APPROVED → REVOKED`; ห้าม re-approve `REVOKED`, ห้าม approve `DEPRECATED` โดยไม่สร้าง version ใหม่
3. เพิ่ม registry snapshot verification: schema version, manifest hash, per-document content hash และ export/import round-trip
4. เพิ่ม index snapshot verification: index hash, registry manifest hash, chunk hash และ scope metadata
5. เพิ่ม adapter scope/Thai support tests
6. ปรับ runner ให้สามารถใช้ registry-backed retrieval fixture โดยยังคง `runtime_authority=NONE` และ `clinical_validity=PENDING`

## ขอบเขตที่ยังไม่ปิด

การ hardening นี้ยังไม่ใช่ runtime semantic vector deployment, human clinical retrieval review, HIS/EMR integration, clinical validation, production approval หรือ external governance sign-off. Persistence ที่เพิ่มเป็น reproducible software artifact เท่านั้น และต้องมี operational access-control/retention decision ก่อนใช้งานจริง
