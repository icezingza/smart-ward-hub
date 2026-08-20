# External Authorization API — Decision Lifecycle Design

**สถานะ:** design contract สำหรับ offline simulator และ future non-production integration; ไม่ใช่ authorization จริง

## 1. Design goals

การออกแบบนี้มีเป้าหมายให้ทุกสถานะที่เกี่ยวกับการส่งเอกสารและการตัดสินใจภายนอก **fail-closed** เมื่อข้อมูลไม่ครบ, หมดอายุ, ถูกเพิกถอน, อ่านจาก version เก่า, เกิด timeout หรือไม่ทราบผลหลังการส่ง โดยต้องไม่เปลี่ยนเหตุการณ์ที่ไม่แน่นอนให้กลายเป็น approval

ระบบท้องถิ่นยังคงตรึง:

```text
external_authority=NONE
clinical_validation_authorized=false
production_authorized=false
runtime_authority=NONE
pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
```

## 2. Submission state machine

| State | Meaning | Allowed next states |
|---|---|---|
| `RECEIVED_FOR_SIMULATION` | รับ package และตรวจ idempotency แล้ว | `IN_SIMULATED_REVIEW`, `SUBMISSION_RECONCILIATION_REQUIRED`, `BLOCKED_SIMULATION` |
| `IN_SIMULATED_REVIEW` | reviewer กำลังตรวจในขอบเขตจำลอง | `REQUIRES_CLARIFICATION`, `DECISION_PENDING_EXTERNAL_VERIFICATION`, `BLOCKED_SIMULATION` |
| `REQUIRES_CLARIFICATION` | ต้องส่งข้อมูลเพิ่มหรือแก้ gap | `IN_SIMULATED_REVIEW`, `BLOCKED_SIMULATION` |
| `DECISION_PENDING_EXTERNAL_VERIFICATION` | มีผลจำลอง/ผลภายนอกที่ยังยืนยัน authenticity/custody ไม่ครบ | `REQUIRES_CLARIFICATION`, `DECISION_EXPIRED`, `DECISION_REVOKED`, `BLOCKED_SIMULATION` |
| `SUBMISSION_RECONCILIATION_REQUIRED` | ไม่ทราบว่า request ถูก commit หรือไม่หลัง timeout/connection failure | `RECEIVED_FOR_SIMULATION`, `BLOCKED_SIMULATION` |
| `DECISION_EXPIRED` | decision หมดอายุแล้ว | `RESUBMISSION_REQUIRED`, `BLOCKED_SIMULATION` |
| `DECISION_REVOKED` | decision ถูกเพิกถอนหรือ superseded | `RESUBMISSION_REQUIRED`, `BLOCKED_SIMULATION` |
| `BLOCKED_SIMULATION` | integrity, schema, authorization boundary หรือ evidence contract ล้มเหลว | `REOPENED_WITH_REASON` |
| `RESUBMISSION_REQUIRED` | ต้องสร้าง version/submission ใหม่ ไม่แก้ record เดิม | `RECEIVED_FOR_SIMULATION` |

ตัวจำลองไม่อนุญาต transition ใด ๆ ไป `AUTHORIZED_BY_EXTERNAL_OWNER` และไม่อนุญาตให้ `DECISION_PENDING_EXTERNAL_VERIFICATION` ถูกตีความเป็น approval

## 3. Decision record

Decision record ที่จะรองรับในอนาคตต้องประกอบด้วย:

| Field | Rule |
|---|---|
| `decision_id` | immutable, unique |
| `submission_id` | ต้อง trace ไป submission ที่ตรวจจริง |
| `manifest_sha256` | ต้องตรงกับ freeze ที่ถูกตรวจ |
| `scope_id` / `window_id` | ต้องตรงกับ scope/test window |
| `decision_status` | `PENDING_EXTERNAL_VERIFICATION`, `REQUIRES_CLARIFICATION`, `ACCEPTED_WITH_RESIDUAL_RISK`, `BLOCKED`, `EXPIRED`, `REVOKED`, `SUPERSEDED` |
| `decision_basis_refs` | evidence/finding refs ที่ตรวจสอบย้อนกลับได้ |
| `decided_by_role` | named external role; local submitter ห้ามเป็นผู้อนุมัติ |
| `decision_timestamp` | timezone-aware และต้องมาจาก trusted source ในระบบจริง |
| `effective_from` / `expires_at` | timezone-aware; `expires_at > effective_from` |
| `signature_ref` / `key_id` | ต้องมี signed response/trust-chain evidence ในระบบจริง |
| `revocation_ref` | จำเป็นเมื่อ status เป็น `REVOKED` หรือ `SUPERSEDED` |
| `rollback_ref` / `stop_authority_ref` | บังคับสำหรับ decision ที่มีผลต่อ test window |
| `independent_verification_ref` | ต้องมี read-back/second-channel evidence |

ใน local simulator ค่า `signature_ref`, `key_id`, `independent_verification_ref` และ external custody ต้องเป็น pending/none และห้ามทำให้ decision กลายเป็น authorized

## 4. Expiry rules

1. ทุก timestamp ต้อง timezone-aware; naive timestamp ถูก reject.
2. ใช้ injected deterministic clock ใน test เพื่อไม่ให้ผลขึ้นกับ wall-clock.
3. client timestamp ไม่ใช่ source of truth; ระบบจริงต้องเก็บ `server_observed_at` และ clock source.
4. หาก `now >= expires_at`, decision ต้องถูกมองว่า expired แม้ client ยัง cache status เก่า.
5. หาก clock skew เกิน policy, สถานะต้องเป็น `CLOCK_UNTRUSTED` หรือ `BLOCKED_SIMULATION` ไม่ใช่ accepted.
6. decision ที่หมดอายุต้องสร้าง version/submission ใหม่ ห้ามแก้ expiry ใน record เดิม.

## 5. Revocation and supersession rules

การเพิกถอนต้องเป็น append-only event ที่อ้าง `decision_id`, reason, actor role, timestamp, effective time และ replacement decision (ถ้ามี). เมื่อพบ revocation:

- invalidate cached status;
- block any pending promotion;
- require read-back acknowledgement;
- retain old decision and hash chain;
- require resubmission or explicit external decision ใหม่;
- never silently revert to a previous accepted state.

## 6. Stale polling rules

Poll request ต้องมี `known_revision` หรือ `known_event_hash` เมื่อระบบจริงรองรับ. หาก response revision ต่ำกว่า known revision, hash chain mismatch หรือ source status stale เกิน TTL ให้คืน:

```text
STALE_RESPONSE_REJECTED
```

และคง local state เป็น blocked/pending จนกว่าจะ reconcile จาก source ที่เชื่อถือได้. Poll เป็น read-only และต้องไม่เปลี่ยน authorization flags

## 7. Timeout, retry and uncertain commit

แบ่งผลล้มเหลวเป็นสามกลุ่ม:

| Failure class | Local action |
|---|---|
| `SAFE_NOT_SENT` | retry ได้ภายใต้ bounded retry budget และ idempotency key เดิม |
| `COMMIT_UNKNOWN` | ห้าม blind retry; เปลี่ยน `SUBMISSION_RECONCILIATION_REQUIRED`, query ด้วย idempotency key และ manifest hash |
| `RESPONSE_UNTRUSTED` | เก็บ response hash, block promotion และขอ independent read-back |

Retry policy ต้องกำหนด maximum attempts, backoff, deadline, correlation ID และการหยุดเมื่อพบ auth/schema/manifest error. Retry ห้ามสร้าง submission ใหม่โดยไม่ตั้งใจ

## 8. Partial commit and transaction boundary

ทุก command ต้องใช้ลำดับ:

1. validate schema, time, authorization, manifest and state;
2. construct candidate state and audit event;
3. verify event hash/chain and appendability;
4. commit state and event atomically;
5. return response with resulting revision/event ID.

หากขั้นตอนใดล้มเหลว ต้องไม่มี state mutation, finding ID reservation หรือ idempotency registration ค้างอยู่ ยกเว้น incident record ที่ระบุความล้มเหลวอย่างชัดเจน

## 9. Audit integrity failure

เมื่อ audit chain ตรวจไม่ได้, event hash เปลี่ยน, sequence ย้อนกลับ หรือ event ขาด ให้เปลี่ยน service state เป็น `AUDIT_INTEGRITY_FAILURE`, block all state-changing commands, preserve forensic snapshot และ require stop-authority/reviewer action. ห้ามตรวจพบความเสียหายภายหลังแล้วดำเนินงานต่อเหมือนไม่มีเหตุการณ์

## 10. Acceptance criteria for next implementation wave

- มี strict state transition map และ typed errors สำหรับทุก invalid transition.
- มี deterministic clock และ expiry tests.
- มี revocation/supersession records และ cache invalidation tests.
- มี stale revision/ETag polling tests.
- มี timeout/uncertain-commit/reconciliation tests.
- มี atomic mutation tests ที่ยืนยัน no partial commit เมื่อ event validation ล้มเหลว.
- มี private/immutable state exposure tests.
- มี audit integrity fail-stop tests.
- ทุก response คง simulation/no-authorization fields.
- ไม่มี path ใดสร้าง clinical, production หรือ external authorization.
