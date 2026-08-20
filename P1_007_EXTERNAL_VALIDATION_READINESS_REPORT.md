# P1-007 External Validation Coordination Readiness Report

**Decision:** `COORDINATION_SOFTWARE_READY`
**Gate count:** `10`
**Initial gate state:** `OPEN=10`, `EVIDENCE_SUBMITTED=0`, `BLOCKED=0`
**External execution:** `NOT_STARTED`
**External owner appointment:** `PENDING_EXTERNAL_APPOINTMENT`
**Real-world authorization:** `false`
**Product status:** `NOT_PRODUCTION_READY`

## Scope

P1-007 is a coordination and evidence-boundary package for the ten external validation gates. It does not perform external validation, appoint external owners, authorize clinical testing, authorize pilot execution or change the production claim.

The coordination package keeps every initial gate `OPEN` until an external owner and accepted evidence process act on it. A gate can become `EVIDENCE_SUBMITTED` only after a valid evidence reference/class/timestamp passes software checks. A `BLOCKED` gate records a visible reason and rejects new evidence until an explicit `reopen` action with a reason.

## Gate matrix

| Gate | Domain | Owner role | External evidence status |
|---|---|---|---|
| GV-01 | Clinical governance | `clinical_owner` | Pending approved protocol, consent/waiver and signed scope |
| GV-02 | Privacy/security | `privacy_security_reviewer` | Pending Zero-PII, retention and access-control review |
| GV-03 | HIS/admission | `integration_owner` | Pending real HIS transcript, FHIR acknowledgment reconciliation and failure recovery |
| GV-04 | Identity/transport | `security_owner` | Pending real OIDC, mTLS handshake and key rotation evidence |
| GV-05 | Fixed Hub host | `host_operator` | Pending Acer hardening, firewall/ACL and service-recovery evidence |
| GV-06 | Hardware recovery | `reliability_owner` | Pending serial loopback, power-loss and disk-full evidence |
| GV-07 | Forensic anchor | `forensic_owner` | Pending external WORM receipt, trusted timestamp and cross-boundary verification |
| GV-08 | Device Trust | `security_owner` | Pending manufacturer provenance, hardware custody and revocation distribution |
| GV-09 | Clinical operations | `ward_manager` | Pending staff training, manual fallback SOP and alarm-fatigue review |
| GV-10 | Independent review | `independent_reviewer` | Pending analysis, adjudication and audit-export evidence |

## Hardening controls

The runtime contract now rejects unsafe package/gate/domain/owner/evidence references, raw identity/contact/secret markers, unsupported clinical/production/accuracy claims, malformed or naive timestamps, duplicate evidence, duplicate blockers, missing blocker reasons, invalid gate registry keys, non-gate evidence records, unexpected execution status, external-owner appointment mutation and any attempt to set clinical or production authorization.

The readiness manifest fixes the gate count and initial state, makes blocker/reopen semantics explicit, requires visible blocker reasons, keeps coordination evidence separate from external proof and fixes the authorization boundary to `NONE`/`false`/`NOT_STARTED`.

## Phase-end verification

The hardening gate runs the existing package regression, gate-matrix regression and new adversarial suite. It mutates manifest status/claim/execution/authorization/counts/tracks/reopen policy, runtime evidence replay, blocked/reopen lifecycle, summary output copies, owner/evidence type, timestamps, secret markers and external execution fields. It also validates the template/schema, scans runtime/readiness artifacts for private-key markers and runs `git diff --check`.

All results are **software coordination verification**. They do not prove any external gate, clinical validation, hardware qualification, independent WORM immutability, real HIS integration, real OIDC/mTLS, manufacturer custody or pilot approval.

## Claim and authorization boundary

The coordination package remains **CONTROLLED_PROTOTYPE_SOFTWARE_EVIDENCE_ONLY_NO_EXTERNAL_AUTHORIZATION**. `clinical_validation_authorized`, `production_authorized` and `real_world_authorization` remain `false`. The pilot gate remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION` and external execution remains `NOT_STARTED`.
