# External Decision Record Readiness Report

**วันที่:** 21 สิงหาคม 2026 (GMT+7)
**Task ID:** `DECISION-RECORD-001`
**สถานะ:** `TEMPLATE_READY_EXTERNAL_VERIFICATION_PENDING`
**Evidence class:** `LOCAL_TEMPLATE` / `EXTERNAL_UNVERIFIED`
**Prepared by role:** `evidence_custodian`
**Independent verification required:** `true`

## 1. ขอบเขต

รอบนี้สร้าง `external_decision_record.py` และ exporter เพื่อกำหนด contract สำหรับ external sign-off record ตาม Wave 0 governance checklist ส่วน decision authenticity, authorization evidence, custody และ required sign-off fields

Contract นี้รับได้เฉพาะ blank-safe template หรือ externally received record ที่ยังจัดเป็น `EXTERNAL_UNVERIFIED`; ไม่เรียก external endpoint, ไม่ตรวจลายเซ็นจริง, ไม่รับรอง reviewer identity และไม่เปลี่ยน authorization state

## 2. Required sign-off fields ที่ถูกบังคับ

| Field group | Fields |
|---|---|
| Identity | `decision_id`, `submission_id`, `record_id` |
| Scope binding | `manifest_sha256`, `scope_id`, `window_id` |
| Decision basis | evidence IDs, finding IDs, residual-risk IDs, condition IDs |
| Authority | `decided_by_role`, `decided_by_ref`, independent verification ref |
| Time | decision timestamp, effective-from, expiry; timezone-aware and ordered |
| Safety | rollback ref, stop-authority ref, revocation ref |
| Authenticity | signature ref, key ID, certificate ref, trust-chain ref and verifier status |
| Boundary | external/clinical/production authorization flags and locked boundary |

## 3. Controls ที่ implement จริง

| Control | พฤติกรรม | สถานะ |
|---|---|---|
| Blank-safe template | ทุก field ที่ต้องมาจากภายนอกเป็น pending/zero-safe | Implemented |
| Decision allowlist | รับเฉพาะ `BLOCKED`, `REQUIRES_CLARIFICATION`, `ACCEPTED_WITH_RESIDUAL_RISK` | Implemented |
| No local verification | `external_decision_verified=false`, verifier status ยัง unverified | Implemented |
| No self-authorization | `authorization_promoted=false`, execution/clinical/production false | Implemented |
| Scope/manifest binding | manifest SHA, scope/window IDs เป็น required fields ใน received record | Implemented |
| Decision basis | อย่างน้อยหนึ่ง evidence/finding/risk/condition reference ต้องมี | Implemented |
| Time safety | timestamps ต้อง timezone-aware และ `effective_from < expires_at` | Implemented |
| Opaque refs | typed refs เท่านั้น, path/URL/raw identity/contact/secret ปฏิเสธ | Implemented |
| Expiry safety | decision timestamp ต้องไม่หลัง expiry | Implemented |
| No duplicate refs | แต่ละ decision-basis list ห้าม duplicate | Implemented |
| No side effect | ไม่มี network/provider/scheduler dependency | Verified by phase-end gate |

## 4. Current local template state

| Field | Value |
|---|---|
| Status | `DECISION_RECORD_TEMPLATE` |
| Decision | `PENDING_EXTERNAL_APPOINTMENT` |
| Evidence class | `LOCAL_TEMPLATE` |
| External decision verified | `false` |
| Authorization promoted | `false` |
| External execution authorized | `false` |
| Clinical validation authorized | `false` |
| External authority | `NONE` |
| Runtime authority | `NONE` |
| Pilot gate | `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION` |

## 5. Verification evidence

| Test/gate | ผล |
|---|---|
| Blank-safe template | PASS |
| Complete received record remains unverified/non-authorizing | PASS |
| Production/authorization promotion rejection | PASS |
| Execution-readiness/PASSED status rejection | PASS |
| Local authenticity promotion rejection | PASS |
| Missing signature/read-back rejection | PASS |
| Expiry and timestamp validation | PASS |
| Raw identity/contact and secret rejection | PASS |
| Non-opaque certificate reference rejection | PASS |
| Numeric-only contact reference rejection | PASS |
| Canonical hash determinism | PASS |
| Exporter snapshot | PASS |
| Phase-end hardening gate | PASS |
| No network/provider side effect scan | PASS |
| Private-key scan | PASS |
| `git diff --check` | PASS |

## 6. Required external verification

ก่อนจะใช้ record ใดเป็น external decision ต้องมี named external authority/reviewer, conflict declaration, signed scope, manifest hash ที่ตรวจจริง, approved window, decision basis, expiry, rollback/stop authority, signature/custody ref, independent read-back และ revocation path จาก trust boundary ภายนอก

Local record ที่มี signature reference แต่ยังไม่มี cryptographic verification หรือ independent read-back ต้องคง `EXTERNAL_UNVERIFIED` และไม่สามารถ authorize pilot, clinical validation หรือ production ได้

## 7. Stop conditions and rollback

ต้องหยุดเมื่อพบ field ขาด, manifest hash ไม่ตรง, scope/window หมดอายุ, signature ตรวจไม่ได้, reviewer conflict ยังไม่แก้, raw identity/secret, role collision, decision status นอก allowlist หรือมีการ mutate authorization flag

Rollback ทำได้โดย revert module, tests, phase-end gate, exporter, report และ master registration จากนั้น rerun Wave 0, Wave E, reviewer preflight, evidence reconciliation, master regression และ release-freeze alignment

## 8. Claim boundary

ผลนี้เป็น **software decision-record contract verification** เท่านั้น ไม่ใช่ external signature verification, reviewer appointment, WORM custody, trusted timestamp, clinical validation หรือ production authorization

สถานะโครงการยังเป็น **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation** และ **clinical validation pending**

## 9. Evidence paths

- `external_decision_record.py`
- `export_external_decision_record.py`
- `test_external_decision_record.py`
- `test_external_decision_record_phase_end_hardening.py`
- `EXTERNAL_DECISION_RECORD_READINESS_REPORT_20260821.md`
- `WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md`
- `evals/micro_rag/evidence/external-decision-record-local-20260821.json`
