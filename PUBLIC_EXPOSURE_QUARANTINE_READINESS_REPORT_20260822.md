# Public-Exposure Quarantine Readiness Report

**วันที่:** 22 สิงหาคม 2026

**Repository:** `icezingza/smart-ward-hub`

**สถานะ:** `PUBLIC_EXPOSURE_QUARANTINED`

## Finding

Repository visibility governance รายงาน `REPOSITORY_VISIBILITY_BLOCKED` เพราะ remote GitHub state เป็น `private=false`. Public-exposure audit จึง fail-closed เป็น `PUBLIC_EXPOSURE_QUARANTINED` แม้ freeze manifest, tracked-file hashes, secret scan และ execution locks จะผ่าน

การตรวจนี้ไม่มีการเรียก GitHub จาก target module, ไม่มีการส่ง evidence, ไม่มีการเปลี่ยน repository setting และไม่มีการ promote authorization. Remote observation ถูกแยกเป็น input evidence จากคำสั่ง `gh repo view` และถูกเก็บแบบ redacted

## Audit results

| Control | Result |
|---|---|
| Freeze manifest present and `PASS` | PASS |
| Frozen files readable | PASS |
| Frozen hashes match | PASS |
| Secret markers absent | PASS |
| Raw identifier patterns absent outside approved synthetic fixtures | PASS |
| Synthetic fixture identifiers classified | PASS; 26 classified findings |
| Private repository confirmed | BLOCKED; `private=false` |
| Authorization boundary | PASS; external authority `NONE` |
| Execution boundary | PASS; submission/promotion/runtime/transmission false |
| Aggregate decision | `PUBLIC_EXPOSURE_QUARANTINED` |
| Primary remediation | `PUBLIC_REPOSITORY_EXPOSURE_QUARANTINED` |

Synthetic identifiers in test, simulation และ presentation fixture paths are reported as `SYNTHETIC_IDENTIFIER_FIXTURE` rather than treated as patient data. Production/source field names such as `patient_token` are not themselves treated as exposed values. Any raw HN/AN-like value outside the approved synthetic path prefixes remains a blocking `IDENTIFIER_PATTERN_FOUND` finding.

## Verification

Focused/adversarial suite ผ่าน 12 cases. Phase-end gate ผ่าน AST scan ที่ไม่พบ network/provider/scheduler/subprocess imports, freeze/hash verification, visibility quarantine, synthetic classification, exporter round-trip, redaction/private-key scan, no-self-authorization และ `git diff --check`. Master regression ผ่านหลังผูก exposure quarantine tests เข้า `run_all_tests.py`

Final release-freeze invariant ผ่าน: `HEAD == origin/main`, `HEAD^ == freeze.source_revision == freeze.origin_main_revision`, `freeze_status=PASS`, tracked-file hashes ตรงกัน, ไม่มี runtime artifacts หลัง cleanup และ working tree สะอาด

## Required remediation

ผู้มีอำนาจต้องยืนยัน external repository-setting operation เพื่อเปลี่ยน repository เป็น private แล้วรัน remote observation ใหม่. หลังจากนั้นต้อง regenerate governance snapshot, public-exposure snapshot และ release freeze พร้อม rerun focused, phase-end และ master regression gates. ห้ามถือว่า local evidence นี้เปลี่ยน visibility ให้แล้ว

จนกว่าจะผ่าน remediation ดังกล่าว ห้ามเก็บ secrets, private keys, credentials, real patient data หรือ external evidence ที่ไม่ควรเผยแพร่ใน repository และห้ามอ้างว่า repository มี private-repository protection

## Product and authorization boundary

ผลนี้เป็น internal software/governance evidence ไม่ใช่ clinical validation, independent review acceptance, external authorization หรือ production approval. สถานะยังคง `external_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false`, `runtime_authority=NONE`, `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`, External Gates `7 BLOCKED / 3 OPEN / 0 PASSED` และ Product `NOT_PRODUCTION_READY`

คำที่อนุญาตคือ **controlled production prototype**, **functional verification passed**, **pilot-ready foundation** และ **clinical validation pending**. ห้ามใช้ **clinical-ready**, **production-ready**, **tamper-proof** หรือ **HIPAA/PDPA compliant 100%** จากผลนี้
