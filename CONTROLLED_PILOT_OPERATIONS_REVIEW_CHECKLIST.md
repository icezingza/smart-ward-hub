# Controlled Pilot Operations — Reviewer Checklist

## A. Package identity and scope

| Check | Required result | Current status |
|---|---|---|
| Package ID and manifest ID are unique | Pass | Review in progress |
| Manifest version is supported | `controlled-pilot-manifest-v1` | Pass |
| Claim boundary is software evidence only | No clinical-ready/production-ready/tamper-proof claim | Pass |
| Product status is stated accurately | controlled production prototype | Pass |
| Clinical and production authorization fields | Both `false` | Pass |
| Runtime authority | `NONE` | Pass |

## B. Evidence integrity

| Check | Required result | Current status |
|---|---|---|
| Artifact exists and SHA-256 matches | Recompute independently | External reviewer action |
| Evidence class is explicit | SOFTWARE_VERIFIED/SIMULATION_ONLY/EXTERNAL_UNVERIFIED/CLINICAL_GOVERNANCE_UNVERIFIED/BLOCKER_RECORD | Pass |
| Collection timestamp has timezone | UTC offset required | Pass |
| `redaction_status` | `PASS` | Pass |
| `prepared_by_role` | Non-personal role identifier | Pass |
| `independent_verification_required` | `true` | Pass |
| Chain-of-custody reference | Present and traceable | External reviewer action |
| Signed-style receipt | Clearly labelled non-cryptographic simulation | Pass |
| External WORM/trusted timestamp | Must not be inferred from local manifest | Pending external evidence |

## C. 10 External Gates

| Gate | Current state | Reviewer action |
|---|---|---|
| GV-01 Clinical Governance & Protocol | `BLOCKED` | Obtain clinical owner/committee decision |
| GV-02 Privacy/Security & Zero-PII Review | `OPEN` | Assign reviewer and collect retention/access evidence |
| GV-03 HIS/Admission Integration | `BLOCKED` | Execute real HIS contract validation |
| GV-04 OIDC/mTLS Identity Transport | `BLOCKED` | Execute real IdP/mTLS/key rotation validation |
| GV-05 Acer Fixed Hub Host Hardening | `OPEN` | Collect target-host hardening evidence |
| GV-06 Serial/Power-Loss/Disk-Full Recovery | `BLOCKED` | Provide controlled non-production fixture, COM evidence and drills |
| GV-07 Independent WORM Forensic Anchor | `BLOCKED` | Provide external receipt/trusted timestamp/cross-boundary verification |
| GV-08 Device Trust & Hardware Key Custody | `BLOCKED` | Provide manufacturer and custody evidence |
| GV-09 Clinical Operations and Manual Fallback | `BLOCKED` | Obtain training/SOP/alarm-fatigue evidence |
| GV-10 Independent Review & Analysis Plan | `OPEN` | Appoint independent reviewer and approve analysis/adjudication plan |

## D. P2-004 model evidence

The reviewer must confirm that each repeated sample uses the same model revision, corpus revision, prompt/retrieval configuration, registry manifest hash, index hash and adapter version. Fixture-direct and registry/index-backed results must not be aggregated.

The reviewer must confirm that provider HTTP 429/5xx and transient transport failures are excluded from the quality denominator but remain evidence-completeness blockers. A single sample per model remains `INSUFFICIENT_SAMPLES`; it cannot be summarized as a reliability or clinical quality score.

## E. Operations gate decision

The current decision is:

```text
operations_state = BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
review_decision = BLOCKED_INCOMPLETE_EVIDENCE
pilot_gate = BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
clinical_validation_authorized = false
production_authorized = false
runtime_authority = NONE
```

The reviewer must not promote the package based on local software tests. Any gate marked `BLOCKED` must be explicitly reopened with a reason before new evidence is submitted. Any external authorization must be recorded outside this software baseline with a named decision owner, signed scope, timestamp, expiry and independent verification reference.

## F. Stop conditions

Stop the review and reopen the package if a raw HN/AN/MRN/National ID appears, a hash mismatch is found, a timestamp lacks timezone, redaction is not `PASS`, an evidence class is missing, a blocker disappears without a transition record, a provider failure is counted as a quality failure, or any local report claims clinical/production authorization.
