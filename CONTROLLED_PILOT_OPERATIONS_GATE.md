# Controlled Pilot Operations Gate & Evidence Export Contract

**สถานะ:** software design baseline; external authorization pending

## 1. วัตถุประสงค์

เอกสารนี้กำหนด operational gate สำหรับการเตรียม controlled pilot ของ Smart Ward Hub โดยเชื่อม product claim boundary, 10 External Gates, GV-10 review decision, P2-004 readiness และ evidence manifest ให้ตรวจสอบย้อนกลับได้ การผ่าน software gate หมายถึง **พร้อมส่งให้ผู้มีอำนาจภายนอกพิจารณา** เท่านั้น ไม่ใช่การอนุมัติ clinical validation, controlled pilot หรือ production deployment

## 2. Gate states

| State | ความหมาย | สิ่งที่อนุญาต |
|---|---|---|
| `NOT_READY` | software หรือ external prerequisite ยังไม่ครบ | แก้ blocker และสร้าง evidence ใหม่ |
| `READY_FOR_EXTERNAL_REVIEW` | local consistency checks ผ่านและ package พร้อมให้ reviewer | ส่ง package ให้ external reviewer |
| `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION` | มี gate blocker, missing owner หรือ authorization boundary | ห้ามเริ่ม controlled pilot |
| `EXTERNAL_REVIEW_IN_PROGRESS` | reviewer ภายนอกรับ package แล้ว | บันทึก findings เท่านั้น |
| `EXTERNAL_DECISION_PENDING` | findings ยังไม่ปิดหรือ decision ยังไม่ลงนาม | ห้าม promote state |
| `AUTHORIZED_BY_EXTERNAL_OWNER` | สงวนไว้สำหรับ signed external decision ที่ระบบนี้ไม่สามารถสร้างเอง | ต้องเก็บ external evidence แยก trust boundary |

สถานะสุดท้ายไม่สามารถสร้างจาก local software function ได้ และไม่มี method ใดใน baseline ที่ตั้ง `clinical_validation_authorized=true` หรือ `production_authorized=true`

## 3. Required controls

Controlled pilot operations package ต้องมีองค์ประกอบต่อไปนี้:

| Control | Required evidence | Local status |
|---|---|---|
| Product claim boundary | product status และ forbidden claims scan | Software verified |
| 10 External Gates | gate ID, owner role, status, blocker และ evidence refs | 7 blocked / 3 open |
| GV-10 review decision | decision status, reviewer role requirement และ traceability | Blocked incomplete evidence |
| P2-004 model evidence | fixed model/corpus/index identity, repeated-sample summary | One live sample per model |
| Runtime readiness | registry/index binding, backend, access control, persistence and governance checks | `NOT_READY` |
| Evidence manifest | file ref, SHA-256, collected-at UTC, provenance and redaction state | Buildable locally |
| Chain of custody | prepared-by role, independent verification required, custody reference | External verification pending |
| Stop condition | explicit blocker and no-authorization decision | Enforced |

## 4. Promotion rules

A local package may be marked `READY_FOR_EXTERNAL_REVIEW` only when its evidence references, hashes, timestamps, gate matrix and decision fields validate. It must remain `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION` when any gate is `BLOCKED`, repeated samples are insufficient, runtime readiness is `NOT_READY`, clinical governance is pending, or an owner/retention/access decision is missing.

No local result may promote `READY_FOR_EXTERNAL_REVIEW` to `AUTHORIZED_BY_EXTERNAL_OWNER`. Promotion requires an externally signed decision, named owner, decision timestamp, scope, expiry and independent verification outside this software baseline.

## 5. Evidence export contract

Each exported evidence item must contain:

- `evidence_id`, `gate_id`, `artifact_ref` and `artifact_sha256`;
- `evidence_class` such as `SOFTWARE_VERIFIED`, `SIMULATION_ONLY`, `EXTERNAL_UNVERIFIED`, `CLINICAL_GOVERNANCE_UNVERIFIED` or `BLOCKER_RECORD`;
- `collected_at_utc` with an explicit timezone;
- `prepared_by_role` and `independent_verification_required=true`;
- `redaction_status=PASS`;
- `chain_of_custody_ref`;
- source boundary and claim boundary;
- manifest version and previous-manifest hash when the export is chained.

The export manifest is **tamper-evident**, not tamper-proof. A local SHA-256 or signed-style simulation does not prove external WORM immutability, trusted timestamping or independent custody.

## 6. Current stop decision

The current Smart Ward Hub package must remain:

- `review_decision=BLOCKED_INCOMPLETE_EVIDENCE`;
- `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`;
- `clinical_validation_authorized=false`;
- `production_authorized=false`;
- `runtime_authority=NONE`.

## 7. Acceptance criteria

1. Invalid state transitions are rejected.
2. A blocked gate cannot be promoted without an explicit reopen transition.
3. Missing or naive timestamps, invalid hashes, missing redaction, raw identity and forbidden claims are rejected.
4. Manifest export is deterministic and chained to the previous manifest when present.
5. Local software cannot self-assign external authorization.
6. Every blocker remains visible in the handoff package and reviewer checklist.
