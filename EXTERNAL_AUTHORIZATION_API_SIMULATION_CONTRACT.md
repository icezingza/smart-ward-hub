# External Authorization API Simulation Contract

**สถานะ:** local deterministic simulation only; ไม่มี network call, credential, external reviewer หรือ authorization จริง
**ขอบเขต:** จำลอง document handoff, submission receipt, status polling, reviewer finding และ audit trail เพื่อทดสอบ integration contract

> API จำลองนี้ไม่ใช่ External Authorization Service จริง และไม่สามารถสร้าง `AUTHORIZED_BY_EXTERNAL_OWNER`, clinical approval หรือ production authorization ได้

## 1. Trust boundary

ตัวจำลองแบ่งเป็นสองบทบาทที่แยกกันอย่างชัดเจน:

| บทบาท | สิ่งที่ทำได้ | สิ่งที่ทำไม่ได้ |
|---|---|---|
| `local_submitter` | ส่ง manifest/evidence package, query status, รับ clarification | อนุมัติ clinical/production, เปลี่ยน external authority, ปลอมลายเซ็น |
| `simulated_external_reviewer` | จำลองรับ package, issue finding และกำหนด `REQUIRES_CLARIFICATION` หรือ `BLOCKED` | สร้าง external authorization จริงหรือยืนยันตัวบุคคลภายนอก |

ทุก response ต้องมี `simulation=true`, `external_authority=NONE` หรือ `SIMULATED_ONLY`, `clinical_validation_authorized=false`, `production_authorized=false` และ `runtime_authority=NONE`

## 2. Simulated endpoints

### `POST /v1/simulated/submissions`

สร้าง submission ใหม่จาก frozen evidence package

**Required request fields**

| Field | Rule |
|---|---|
| `submission_idempotency_key` | unique และห้าม reuse กับ payload ต่างกัน |
| `package_id` | ต้องตรงกับ local Wave 0 package |
| `manifest_version` | positive integer |
| `manifest_sha256` | lowercase SHA-256 64 hex characters |
| `scope_id` / `window_id` | ต้องมีและสัมพันธ์กับ freeze record |
| `artifact_refs` | non-empty, repository/external references ที่ไม่ใช่ raw identity |
| `submitted_by_role` | approved role; โดยทั่วไป `evidence_custodian` |
| `claim_boundary` | ต้องระบุว่าเป็น software/simulation evidence และ no authorization |
| `external_verification_required` | ต้องเป็น `true` |

**Simulated response**

```json
{
  "submission_id": "sim-submission-...",
  "status": "RECEIVED_FOR_SIMULATION",
  "simulation": true,
  "external_authority": "NONE",
  "clinical_validation_authorized": false,
  "production_authorized": false,
  "runtime_authority": "NONE",
  "audit_event_id": "sim-audit-..."
}
```

### `GET /v1/simulated/submissions/{submission_id}`

อ่านสถานะโดยไม่เปลี่ยน state

สถานะที่อนุญาตคือ:

`RECEIVED_FOR_SIMULATION → IN_SIMULATED_REVIEW → REQUIRES_CLARIFICATION | BLOCKED_SIMULATION | DECISION_PENDING_EXTERNAL_VERIFICATION`

ไม่มี transition ไป `AUTHORIZED_BY_EXTERNAL_OWNER` ใน local simulator

### `POST /v1/simulated/submissions/{submission_id}/findings`

สร้าง finding แบบจำลองโดย actor ที่เป็น `simulated_external_reviewer`

Required fields: `finding_id`, `severity`, `category`, `summary`, `evidence_refs`, `required_action`, `reviewer_role`, `reviewer_identity_ref`, `external_verification_status`

Finding ต้อง:

- trace กลับไปยัง `submission_id`, `manifest_sha256`, `scope_id`, `window_id` และ evidence IDs;
- ไม่มี raw HN/AN/MRN/National ID;
- ไม่ใช้ claim `clinical-ready`, `production-ready`, `tamper-proof` หรือ `AUTHORIZED` ใน summary;
- ใช้ `external_verification_status=PENDING_EXTERNAL_VERIFICATION` ใน simulation;
- ถ้า evidence ขาดหรือเป็น local-only ให้ผล `REQUIRES_CLARIFICATION` หรือ `BLOCKED_SIMULATION`

### `GET /v1/simulated/submissions/{submission_id}/audit`

ส่ง audit trail แบบ append-only simulation:

| Field | Requirement |
|---|---|
| `audit_event_id` | unique |
| `occurred_at` | timezone-aware |
| `actor_ref` | opaque role/reference; ไม่ใช้ raw identity |
| `action` | submit, poll, review_start, finding_issued, clarification, status_transition |
| `submission_id` | traceable |
| `previous_event_hash` | hash-chain reference |
| `event_hash` | SHA-256 ของ canonical event |
| `simulation` | `true` |
| `external_authority` | `NONE` หรือ `SIMULATED_ONLY` |

Local audit hash chain เป็น **tamper-evident simulation** เท่านั้น ไม่ใช่ external WORM หรือ trusted timestamp

## 3. Idempotency and replay rules

การส่ง payload เดิมด้วย `submission_idempotency_key` เดิมต้องคืน submission เดิมโดยไม่สร้าง submission ซ้ำ หาก key เดิมมาพร้อม manifest hash, package ID หรือ scope ต่างกัน ต้อง reject แบบ fail-closed

การส่ง finding ID ซ้ำต้องคืน error `DUPLICATE_FINDING`; การ poll ซ้ำต้องไม่ mutate state; การส่ง finding หลัง `BLOCKED_SIMULATION` หรือ `DECISION_PENDING_EXTERNAL_VERIFICATION` ต้อง reject หรือเปิด clarification version ใหม่เท่านั้น

## 4. Negative-path contract

ตัวจำลองต้อง reject กรณีต่อไปนี้:

| Mutation | Expected result |
|---|---|
| raw identity ใน artifact ref, summary หรือ actor ref | `REJECTED_RAW_IDENTITY` |
| manifest hash ไม่ตรง frozen manifest | `REJECTED_MANIFEST_MISMATCH` |
| scope/window ไม่ตรง freeze | `REJECTED_SCOPE_WINDOW_MISMATCH` |
| naive timestamp | `REJECTED_TIMEZONE_REQUIRED` |
| `external_verification_required=false` | `REJECTED_VERIFICATION_BYPASS` |
| `clinical_validation_authorized=true` จาก local submitter | `REJECTED_AUTHORIZATION_ESCALATION` |
| `production_authorized=true` จาก local submitter | `REJECTED_AUTHORIZATION_ESCALATION` |
| claim `AUTHORIZED_BY_EXTERNAL_OWNER` ใน local payload | `REJECTED_FORBIDDEN_CLAIM` |
| idempotency key reused กับ payload ต่างกัน | `REJECTED_IDEMPOTENCY_CONFLICT` |
| audit event แก้ย้อนหลัง | `REJECTED_AUDIT_MUTATION` |

## 5. External decision boundary

ผลที่ simulator ออกได้สูงสุดคือ `DECISION_PENDING_EXTERNAL_VERIFICATION`, `REQUIRES_CLARIFICATION` หรือ `BLOCKED_SIMULATION` โดยต้องคง:

```text
external_authority=NONE
clinical_validation_authorized=false
production_authorized=false
runtime_authority=NONE
pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
```

`AUTHORIZED_BY_EXTERNAL_OWNER` ต้องมาจากระบบ/คณะกรรมการภายนอกที่มีหลักฐานลายเซ็น, named owner, decision timestamp, scope, expiry, rollback, stop authority และ independent verification นอก repository นี้

## 6. Audit and evidence retention

Simulation report ต้องเก็บ request/response hashes, event chain, status transitions, rejected mutations, final decision และ source boundary โดยไม่เก็บ raw identity หรือ credential. ผลของ simulator จัดเป็น `SIMULATION_ONLY` และใช้เป็น integration evidence เท่านั้น

## 7. Acceptance criteria

1. Submit/poll/findings/audit lifecycle ทำงาน deterministic และ replay-safe.
2. Submission เดิม idempotent; payload ต่างกันภายใต้ key เดิมถูก reject.
3. ทุก status response แสดง simulation/no-authorization fields.
4. Manifest, scope, window และ evidence traceability ถูกตรวจครบ.
5. Negative mutations ทั้งหมด fail-closed.
6. Audit hash chain ตรวจสอบได้และ reject mutation.
7. Simulator ไม่เปิด network และไม่มี external credential.
8. ไม่มี path ใดสร้าง clinical, production หรือ external authorization.

## 8. v2 Wave A–D fail-closed hardening requirements

ตัวจำลอง v2 หลังการ harden เพิ่ม controls ที่ต้องถือเป็น **P0-hardened software baseline** สำหรับ integration contract:

| Wave/control | Behavior | Claim class |
|---|---|---|
| A — Atomic transition | validate → build candidate → build audit event → commit; timestamp/audit failure ต้องไม่ทิ้ง partial state | Software verified |
| A — Private state and serialization | private submissions/audit store, defensive snapshots, monotonic sequence และ deterministic lock serialization | Software verified |
| A — Audit incident fail-stop | chain tamper สร้าง incident ID, `recovery_required=true`, service state `AUDIT_INTEGRITY_FAILURE` และ block state-changing commands | Simulation-only |
| B — Decision lifecycle | รองรับ pending, expiry, revocation และ resubmission boundary พร้อม decision revision/cache version | Simulation-only |
| B — Stale/cache/restart | ตรวจ known revision/event hash/cache version และใช้ hashed snapshot export/import ที่ bind กับ frozen package | Software verified/partial |
| C — Delivery uncertainty | `COMMIT_UNKNOWN`, reconciliation และ bounded retry advice ที่แยก retry กับ reconcile | Simulation-only |
| C — Chunk/audit bounds | bounded chunk manifest, contiguous sequence, per-chunk hash, received/finalize check, allowlisted audit payload และ event-size limit | Software verified/partial |
| C — Strict schema | reject unknown fields, wrong types, malformed hash, invalid role/severity/ref, untraceable evidence และ oversized values | Software verified |
| D — Governance binding | constructor ตรวจ governance state, validation snapshot, freeze record และ locked authorization boundary | Software verified/partial |
| D — Authenticity/version guard | exact contract negotiation; simulator ปฏิเสธ response ที่อ้าง local/external authorization และคืน `SIMULATION_ONLY`/untrusted result | Simulation-only |

v2 ยังคงเป็น in-memory simulator จึงไม่ยืนยัน durable database transaction, process restart ของ production service, TLS/mTLS, OIDC, ACL, external WORM, trusted time, reviewer identity หรือ real network behavior. ช่องว่างทั้งหมดอยู่ใน `EXTERNAL_AUTHORIZATION_API_FAIL_CLOSED_GAP_REGISTER.md`

## 9. Wave E evidence record and dossier-state boundary

Wave E ใช้ `wave-e-evidence-v1` เป็น record-level evidence contract. JSON Schema และ state transition manifest อยู่ที่ `evals/micro_rag/evidence/wave-e-evidence-schema-v1.json`; strict implementation อยู่ที่ `external_authorization_api_wave_e_evidence.py` และ regression อยู่ที่ `test_wave_e_evidence.py`.

Record ที่พร้อม independent review ต้องมี test run/case identity, expected/actual result, failure class, ordered timezone-aware timestamps, clock source/skew result, endpoint environment and TLS identity references, correlation/idempotency hashes, request/response/artifact/manifest hashes, remote receipt and reconciliation result, signature/key/read-back evidence, scope/window/expiry/revocation, stop/recovery separation-of-duties fields, topology/worker/limiter semantics, chain of custody and role provenance. Unknown fields, naive timestamps, incomplete signature/read-back, unresolved `COMMIT_UNKNOWN`, invalid topology และ authorization mutations ต้องถูก reject.

Dossier coordination state แยกจาก simulator API `STATUSES` และไม่ใช่ authorization state:

```text
EXTERNAL_VALIDATION_NOT_STARTED
 -> READY_FOR_EXTERNAL_OWNER_APPOINTMENT
 -> READY_FOR_EXTERNAL_EXECUTION
 -> IN_EXECUTION
 -> READY_FOR_INDEPENDENT_REVIEW
 -> CLOSED_NO_AUTHORIZATION
```

การกลับจาก `BLOCKED` ทำได้ด้วย explicit reopen/reason เท่านั้น; `CLOSED_NO_AUTHORIZATION` เป็น terminal coordination state และไม่มี local transition ไปสู่ external, clinical, production หรือ runtime authority.

## 10. Wave E external validation boundary

ก่อนจะเปลี่ยน claim หรือ gate status ต้องมีการทดสอบ non-production กับ external endpoint จริง โดยมี named owner, approved test window, stop authority, OIDC/mTLS transcript, ACL decision, signed response verification, expiry/revocation propagation, timeout/retry transcript, independent read-back และ custody evidence. Local simulator, local snapshot หรือ local hash chain ไม่สามารถแทนหลักฐานดังกล่าวได้
