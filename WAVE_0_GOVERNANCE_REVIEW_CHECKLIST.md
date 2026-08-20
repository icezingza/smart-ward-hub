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
