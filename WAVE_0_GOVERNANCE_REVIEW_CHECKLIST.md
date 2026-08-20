# Wave 0 Governance Review Checklist

**สถานะ:** ใช้สำหรับเตรียม external review; ยังไม่ใช่ authorization record
**Package:** Smart Ward Hub Wave 0 Governance Handoff

## A. Role appointment

| Check | Evidence required | Local status | External reviewer result |
|---|---|---|---|
| Clinical owner appointed | External appointment record และ scope | Pending external verification | ☐ Accept ☐ Clarify ☐ Reject |
| Independent reviewer appointed | Conflict declaration และ appointment evidence | Pending external verification | ☐ Accept ☐ Clarify ☐ Reject |
| Stop authority appointed | Authority to stop test window, notification path | Pending external verification | ☐ Accept ☐ Clarify ☐ Reject |
| Evidence custodian appointed | Custody and freeze responsibility | Pending external verification | ☐ Accept ☐ Clarify ☐ Reject |
| Security/integration/reliability/forensic/ward roles assigned | Role-specific responsibility and expiry | Pending external verification | ☐ Accept ☐ Clarify ☐ Reject |

## B. Scope and test window

| Check | Required condition | Local status | Reviewer result |
|---|---|---|---|
| Signed scope | In-scope/out-of-scope, environment and purpose are explicit | Local schema verified; signature pending | ☐ Accept ☐ Clarify ☐ Reject |
| Expiry | Scope and appointment expiry are timezone-aware | Local schema verified | ☐ Accept ☐ Clarify ☐ Reject |
| Rollback | Reversible steps and owner are named | Local reference present; external owner pending | ☐ Accept ☐ Clarify ☐ Reject |
| Test window | Start/end, allowlists, data class and operator roles are explicit | Local schema verified | ☐ Accept ☐ Clarify ☐ Reject |
| Stop criteria | Safety, privacy, identity, infrastructure, evidence and governance triggers exist | Local schema verified | ☐ Accept ☐ Clarify ☐ Reject |
| Data boundary | Default is synthetic/non-PII | Software verified | ☐ Accept ☐ Clarify ☐ Reject |

## C. Evidence-register freeze

| Check | Required condition | Local status | Reviewer result |
|---|---|---|---|
| Manifest hash | Deterministic SHA-256 over canonical entries | Software verified/simulated | ☐ Accept ☐ Clarify ☐ Reject |
| Freeze identity | Freeze ID, version, timestamp, custodian role | Software verified/simulated | ☐ Accept ☐ Clarify ☐ Reject |
| Append-only policy | Mutation requires new version, previous hash and reason | Software contract verified | ☐ Accept ☐ Clarify ☐ Reject |
| Custody | External custody or trusted timestamp is independently evidenced | Not verified | ☐ Accept ☐ Clarify ☐ Reject |
| Redaction | No raw HN/AN/MRN/National ID in manifest | Software scan verified | ☐ Accept ☐ Clarify ☐ Reject |
| Claim boundary | Local receipt is not called WORM, tamper-proof or cryptographic signature | Software contract verified | ☐ Accept ☐ Clarify ☐ Reject |

## D. External authorization decision

The reviewer must not treat local validation as authorization. A positive external decision must identify the authorized scope, named external owner, decision timestamp, expiry, rollback, stop authority and independent verification reference.

| Decision | Meaning |
|---|---|
| `BLOCKED_INCOMPLETE_GOVERNANCE` | Required appointments, scope or test-window records are missing |
| `READY_FOR_EXTERNAL_GOVERNANCE_REVIEW` | Local package is internally coherent and ready to send; no authorization granted |
| `REQUIRES_CLARIFICATION` | Reviewer needs additional evidence or correction |
| `ACCEPTED_WITH_RESIDUAL_RISK` | External reviewer accepts stated residual risks within a bounded scope |
| `AUTHORIZED_BY_EXTERNAL_OWNER` | Reserved for a signed external decision outside this repository |
| `REJECTED` | Package or scope is unacceptable |

## E. Stop and escalation rules

Stop immediately if raw identity appears, a scope expires, an untrained operator acts, a test leaves the allowlisted environment, a hash changes after freeze, real credentials are exposed, a clinical workflow is entered without approval, or a local report is used to claim external authorization.

The local package must remain:

- `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`;
- `clinical_validation_authorized=false`;
- `production_authorized=false`;
- `runtime_authority=NONE`;
- `external_authority=NONE`.

## F. External Authorization API handoff and transport

> ส่วนนี้เป็นข้อกำหนดสำหรับ **ระบบภายนอกจริง**; simulated API ใน repository ตรวจได้เพียง schema, idempotency และ no-authorization behavior ไม่สามารถยืนยัน transport หรือสิทธิ์จริงได้

| Check | Required external evidence | Local/simulation status | Reviewer result |
|---|---|---|---|
| API identity and endpoint | Approved service owner, environment/tenant identifier, API version, endpoint allowlist and change owner | Simulation only; no network endpoint | ☐ Accept ☐ Clarify ☐ Reject |
| Client authentication | OIDC/mTLS profile, certificate chain, key ID, rotation/revocation procedure and failed-auth transcript | Not verified | ☐ Accept ☐ Clarify ☐ Reject |
| Client authorization | Role-to-endpoint matrix, least-privilege scope, reviewer versus submitter separation and deny transcript | Simulation boundary verified; external ACL pending | ☐ Accept ☐ Clarify ☐ Reject |
| Transport protection | TLS/mTLS configuration, trust anchor, hostname verification, protocol version and isolated test transcript | Not verified | ☐ Accept ☐ Clarify ☐ Reject |
| Idempotency | Repeated request returns original submission; changed payload under same key is rejected | Simulation verified | ☐ Accept ☐ Clarify ☐ Reject |
| API version/change control | Contract version, schema compatibility policy, migration/rollback plan and deprecation notice path | Not verified | ☐ Accept ☐ Clarify ☐ Reject |
| Rate limit and retry behavior | Agreed limits, backoff rules, retry safety, `429`/timeout handling and duplicate prevention | Simulation does not model external limits | ☐ Accept ☐ Clarify ☐ Reject |
| Network failure behavior | Partial upload, connection reset, timeout and uncertain-commit reconciliation procedure | Simulation does not prove network behavior | ☐ Accept ☐ Clarify ☐ Reject |

## G. Status, decision authenticity and authorization evidence

| Check | Required condition | Local/simulation status | Reviewer result |
|---|---|---|---|
| Monotonic status state machine | Status transitions are documented, invalid transitions are rejected and polling is read-only | Simulation verified | ☐ Accept ☐ Clarify ☐ Reject |
| Status freshness | `occurred_at`, `observed_at`, source clock, timezone and stale-response handling are explicit | Simulation uses timezone-aware timestamps; external clock pending | ☐ Accept ☐ Clarify ☐ Reject |
| Response authenticity | Decision response has signature/MAC, key ID, certificate/trust-chain reference and verification result | Not verified; simulation authority is `NONE` | ☐ Accept ☐ Clarify ☐ Reject |
| Reviewer authority | Named external reviewer, organization authority, conflict declaration and appointment evidence | Pending external verification | ☐ Accept ☐ Clarify ☐ Reject |
| Decision scope | Decision identifies package/manifest hash, scope ID, test-window ID, allowed systems/devices and exclusions | Local traceability verified; external decision pending | ☐ Accept ☐ Clarify ☐ Reject |
| Decision expiry | Decision has explicit timezone-aware effective/expiry timestamps and renewal path | Not verified | ☐ Accept ☐ Clarify ☐ Reject |
| Conditional approval | Conditions, residual risks, required controls and owners are recorded; unresolved conditions keep pilot blocked | Simulation produces clarification/block states | ☐ Accept ☐ Clarify ☐ Reject |
| Revocation | Revocation trigger, authority, propagation path, acknowledgement and post-revocation behavior are tested | Not verified | ☐ Accept ☐ Clarify ☐ Reject |
| No self-authorization | Local submitter cannot set clinical/production flags or claim external authority | Simulation verified; must be confirmed at real API boundary | ☐ Accept ☐ Clarify ☐ Reject |

## H. Audit, evidence custody and operational failure handling

| Check | Required evidence | Local/simulation status | Reviewer result |
|---|---|---|---|
| Submission audit | Request ID, idempotency key, actor role/reference, package hash, response hash and correlation ID | Simulation verified | ☐ Accept ☐ Clarify ☐ Reject |
| Status-poll audit | Poll is read-only, records source status/version and detects stale or conflicting responses | Simulation partially verified; external API pending | ☐ Accept ☐ Clarify ☐ Reject |
| Decision audit | Finding/decision links to evidence IDs, manifest hash, scope, window, reviewer and decision record | Simulation traceability verified | ☐ Accept ☐ Clarify ☐ Reject |
| External custody | Independent WORM/append-only receipt, trusted timestamp and read-back verification | Not verified | ☐ Accept ☐ Clarify ☐ Reject |
| Clock integrity | Time source, synchronization, acceptable skew and behavior after clock failure are documented | Not verified | ☐ Accept ☐ Clarify ☐ Reject |
| Error and incident handling | Incident severity, notification channel, containment, evidence preservation, retry/rollback and escalation owner | Local stop contract exists; external channel pending | ☐ Accept ☐ Clarify ☐ Reject |
| Data retention/deletion | Retention owner, legal/clinical policy, deletion hold, export and destruction evidence are approved | Local persistence contract only; external approval pending | ☐ Accept ☐ Clarify ☐ Reject |
| Disaster recovery | Backup/restore, key recovery, API outage procedure, reconciliation and manual fallback are tested | Software controls exist; external drill pending | ☐ Accept ☐ Clarify ☐ Reject |
| Independent read-back | Reviewer verifies the submitted manifest and decision from an independent channel or custody store | Not verified | ☐ Accept ☐ Clarify ☐ Reject |

## I. Required external sign-off record

ผู้ตรวจสอบภายนอกต้องไม่ลงนามเพียงว่า “ผ่านระบบ” แต่ต้องระบุ decision record ที่ตรวจสอบย้อนกลับได้:

| Field | Required value |
|---|---|
| `decision_id` | Unique immutable decision ID |
| `submission_id` | ตรงกับ handoff submission |
| `manifest_sha256` | ตรงกับ freeze ที่ตรวจจริง |
| `scope_id` / `window_id` | ตรงกับขอบเขตและ test window ที่อนุมัติ |
| `decision` | `BLOCKED`, `REQUIRES_CLARIFICATION`, `ACCEPTED_WITH_RESIDUAL_RISK` หรือ reserved external authorization decision |
| `decision_basis` | Evidence IDs, findings, residual risks และ conditions |
| `decided_by_role` | Named external authority role |
| `decision_timestamp` | Timezone-aware และตรวจ source clock ได้ |
| `effective_from` / `expires_at` | ขอบเขตเวลาที่ชัดเจน |
| `rollback_ref` / `stop_authority_ref` | อ้างอิงแผน rollback และผู้สั่งหยุด |
| `signature_ref` | External signature/custody reference |
| `independent_verification_ref` | ผู้ตรวจซ้ำหรือช่องทาง read-back ที่เป็นอิสระ |
| `revocation_ref` | วิธีเพิกถอนและการแจ้งเตือน |

หาก field ใดขาด, hash ไม่ตรง, scope หมดอายุ, signature ตรวจไม่ได้, reviewer มี conflict ที่ยังไม่แก้ หรือเงื่อนไข approval ยังไม่ครบ ให้คงสถานะ `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`

## J. API simulation boundary

`external_authorization_api_simulator.py` และรายงาน simulation สามารถยืนยันได้เฉพาะ document handoff lifecycle, deterministic polling, idempotency, finding traceability, audit hash-chain, Wave A–D software controls และ fail-closed mutations ใน memory เท่านั้น ผลดังกล่าวต้องจัดเป็น `SOFTWARE_VERIFIED` หรือ `SIMULATION_ONLY` ตาม control และห้ามใช้แทนหลักฐาน OIDC/mTLS, external WORM, trusted timestamp, real reviewer identity, clinical governance หรือ production authorization

## K. v2 fail-closed simulator review

ส่วนนี้ใช้ตรวจว่า software simulator รองรับ failure semantics ที่จำเป็นก่อนนำ contract ไปทดสอบกับ external API จริง:

| Check | Required condition | Current status | Reviewer result |
|---|---|---|---|
| Atomic state transition | Naive timestamp, audit failure หรือ schema failure ต้องไม่เปลี่ยน submission/finding/status ค้าง | Software verified by v2 regression | ☐ Accept ☐ Clarify ☐ Reject |
| Private state exposure | Caller แก้ `submissions`/`audit_events` จาก snapshot ที่คืนไม่ได้ | Software verified by v2 regression | ☐ Accept ☐ Clarify ☐ Reject |
| Expiry | `now >= expires_at` เปลี่ยนเป็น `DECISION_EXPIRED` และไม่ใช้ cache เก่า | Simulation verified; external clock pending | ☐ Accept ☐ Clarify ☐ Reject |
| Revocation | revoke ต้องมี decision ID/reason และ block invalid follow-up | Simulation verified; external propagation pending | ☐ Accept ☐ Clarify ☐ Reject |
| Stale polling | revision/hash เก่าถูก reject และไม่เลื่อน authorization | Software verified by v2 regression | ☐ Accept ☐ Clarify ☐ Reject |
| Commit uncertainty | timeout หลัง commit ต้องเข้า reconciliation ไม่ blind retry | Simulation verified; network transcript pending | ☐ Accept ☐ Clarify ☐ Reject |
| Audit fail-stop | chain tamper block state-changing command และสร้าง incident boundary | Simulation verified; durable append-only store pending | ☐ Accept ☐ Clarify ☐ Reject |
| Concurrency serialization | concurrent commands มี monotonic event sequence และไม่สร้าง duplicate state | Software verified by Wave A regression | ☐ Accept ☐ Clarify ☐ Reject |
| Cache/restart recovery | cache version, package-bound snapshot hash และ invalid snapshot fail-closed | Software verified/partial; distributed propagation pending | ☐ Accept ☐ Clarify ☐ Reject |
| Chunk integrity | bounded count/size, contiguous sequence, per-chunk hash และ incomplete finalize ถูก reject | Software verified/partial; real upload transport pending | ☐ Accept ☐ Clarify ☐ Reject |
| Governance binding | local package ต้องอยู่ใน review-ready state, freeze/validation boundary และ authorization flags locked | Software verified/partial; external appointments pending | ☐ Accept ☐ Clarify ☐ Reject |
| Response authenticity | local/external authorization response ถูก reject; result ต้อง `trusted=false` จนกว่าจะมี signature/read-back จริง | Simulation-only denial; real trust chain pending | ☐ Accept ☐ Clarify ☐ Reject |
| Contract version | unsupported version ถูก reject และ exact match ถูกบันทึก | Software verified by Wave D regression | ☐ Accept ☐ Clarify ☐ Reject |
| Strict schema | wrong type, unknown field, oversized field, invalid enum/hash/role ถูก reject | Software verified by v2 regression | ☐ Accept ☐ Clarify ☐ Reject |

## L. Production-readiness evidence audit

| Domain | Required evidence before production claim | Current classification | Decision |
|---|---|---|---|
| Code and regression | Source, targeted tests, master regression and reproducible run transcript | Implemented software baseline | ☐ Accept ☐ Clarify ☐ Reject |
| Configuration | Pilot environment, disabled docs, loopback/allowlist, out-of-tree runtime paths, OIDC shape | Implemented validator; real environment pending | ☐ Accept ☐ Clarify ☐ Reject |
| Real identity transport | Real IdP/HIS OIDC/mTLS handshake, claims, rotation, revocation and network segmentation | Unverified | ☐ Accept ☐ Clarify ☐ Reject |
| Host and physical hardware | Acer account/ACL, encryption, firewall, patch state, time, COM, power-loss, disk-full and recovery | Unverified | ☐ Accept ☐ Clarify ☐ Reject |
| Backup/restore | Encrypted destination, retention owner, RPO/RTO, isolated restore and post-restore verification | Software verified; external destination pending | ☐ Accept ☐ Clarify ☐ Reject |
| Forensic anchoring | Independent append-only/WORM receipt, trusted time, key custody and read-back | Unverified | ☐ Accept ☐ Clarify ☐ Reject |
| Clinical governance | Protocol, clinical owner/committee decision, consent/waiver, human-factors and shadow-mode review | Unverified | ☐ Accept ☐ Clarify ☐ Reject |
| Operational authorization | 10 gates, reviewer decision, expiry, revocation, stop authority and rollback record | Blocked: 7 BLOCKED, 3 OPEN, 0 PASSED | ☐ Accept ☐ Clarify ☐ Reject |

Production claim remains prohibited until every applicable domain has named owner, external evidence, independent verification and explicit decision record. Local v2 simulator output remains `SIMULATION_ONLY`.
