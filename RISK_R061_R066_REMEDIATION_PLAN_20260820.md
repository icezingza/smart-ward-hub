# Risk R-061 ถึง R-066 — Remediation Plan

**ตรวจจาก commit baseline:** `6d5343bc2cbda14b9a3f71294ab0607e2acb1aab`

**ขอบเขต:** software hardening และ evidence validation สำหรับ Wave E เท่านั้น ไม่ใช่ external validation, clinical authorization หรือ production authorization

## Risk disposition

| Risk | Severity | Current software control | Residual external dependency | Acceptance evidence สำหรับรอบถัดไป |
|---|---|---|---|---|
| R-061 | High | strict per-record fields มีแล้ว | ต้องมี record ครบ T-01 ถึง T-12 จาก external owner | aggregate validator ปฏิเสธ test-case ซ้ำ/ขาด/นอก T-01..T-12 และตรวจ expected/actual/failure ครบ |
| R-062 | Critical | signature/key/hash/read-back fields มีแล้ว | real trust chain, key custody และ independent second-channel read-back | record validator บังคับ field coherence; `READY_FOR_INDEPENDENT_REVIEW` ห้ามผ่านถ้า signature/read-back ไม่ครบ |
| R-063 | Critical | idempotency/reconciliation fields มีแล้ว | durable remote receipt/status query และ real timeout transcript | `COMMIT_UNKNOWN` ต้องมี reconciliation result + receipt; aggregate ห้ามมี unresolved uncertainty |
| R-064 | High | timezone-aware ordered timestamps มีแล้ว | trusted external clock, skew policy และ expiry/revocation propagation | validator ตรวจ ordering, expiry, observed time และ clock skew policy ของทุก record |
| R-065 | High | topology/worker/limiter fields มีแล้ว | real multi-worker/multi-node coordinated limiter | validator ปฏิเสธ single-process ที่ worker > 1 และบังคับ topology metadata ในทุก record |
| R-066 | Critical | stop/recovery fields มีบางส่วน; role appointment อยู่ใน dossier | external separation of duties และ independent authority | validator บังคับ distinct prepared/owner/verifier/stop/recovery roles เมื่อ record พร้อม review |

## Software changes approved for this phase

1. เพิ่ม `WaveEEvidenceBundle` aggregate validator เพื่อบังคับ coverage ของ T-01 ถึง T-12, duplicate protection, cross-record boundary และ fail-closed promotion.
2. เพิ่ม role separation fields สำหรับ evidence custodian, independent verifier, stop authority และ recovery approver พร้อม distinct-role checks ใน review-ready state.
3. เพิ่ม cross-record checks สำหรับ one `test_run_id`, one scope/window, consistent contract/schema version, consistent no-authorization boundary และ no raw identity.
4. เพิ่ม regression สำหรับ missing/duplicate test cases, role collision, unresolved `COMMIT_UNKNOWN`, inconsistent hash/scope/time/authorization metadata และ invalid promotion.
5. อัปเดต evidence JSON, handoff, risk register และ dossier; local result ยังคง `READY_FOR_EXTERNAL_OWNER_APPOINTMENT`, external execution `NOT_STARTED`.

## Explicit non-goals

การแก้ไขรอบนี้จะไม่สร้าง external endpoint, ไม่เรียก OIDC/JWKS หรือ mTLS จริง, ไม่เปลี่ยน `external_authority=NONE`, ไม่เปลี่ยน `clinical_validation_authorized=false`, ไม่เปลี่ยน `production_authorized=false`, ไม่เปลี่ยน `runtime_authority=NONE` และไม่เปลี่ยน External Gate เป็น `PASSED`.

## Implementation result — 2026-08-20

Software hardening รอบนี้ดำเนินการแล้วใน `external_authorization_api_wave_e_evidence.py`:

- `WaveEEvidenceBundle` บังคับ exactly one record ต่อ `T-01` ถึง `T-12` พร้อม duplicate/missing/out-of-scope rejection.
- ทุก record ใน bundle ต้องมี `test_run_id`, `scope_id`, `window_id` และ `contract_version=external-auth-sim-v2` ที่สอดคล้องกัน.
- ทุก record ต้องอยู่ใน `READY_FOR_INDEPENDENT_REVIEW` และคง no-authorization boundary.
- Role separation ถูกบังคับให้ `prepared_by_role=evidence_custodian_role` และแยก `external_owner_role`, `independent_verifier_role`, `stop_authority_role`, `recovery_approver_role` ออกจากกัน.
- Record-level stop/recovery roles ต้องตรงกับ declared authority roles และ stop/recovery approver ห้ามเป็น role เดียวกัน.
- JSON Schema/state manifest ถูก regenerate และ `test_wave_e_evidence.py` ผ่าน รวม bundle negative cases.

ผลล่าสุด: Wave E targeted regression และ dependent GV-10/Wave 0/production-audit regression ผ่าน; ผลนี้เป็น `SOFTWARE_VERIFIED/SIMULATION_ONLY` เท่านั้น. External trust chain, durable remote receipt, trusted external clock, deployment limiter และ external separation of duties ยัง `EXTERNAL_UNVERIFIED`.
