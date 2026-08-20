# P1-006 Clinical Validation Readiness Report

**Decision:** `CLINICAL_VALIDATION_SOFTWARE_PREFLIGHT_READY`
**Preflight status:** `READY_FOR_EXTERNAL_GOVERNANCE_REVIEW`
**Execution status:** `NOT_STARTED`
**Clinical governance:** `PENDING`
**Clinical validation:** `PENDING`
**Real-world authorization:** `false`
**Product status:** `NOT_PRODUCTION_READY`

## Scope

P1-006 is a software preflight and evidence-preparation package. It checks whether an intended clinical-validation plan records the required protocol, owners, privacy, consent or waiver, operational safety, fallback, recovery, device, identity transport, HIS, independent review and analysis gates. It does not authorize clinical validation, testing with real patients, treatment workflow or production use.

The downstream decision remains with clinical governance and the hospital's approved process. A complete software preflight stops at `READY_FOR_EXTERNAL_GOVERNANCE_REVIEW`; it does not produce a clinical approval.

## Software-preparation tracks

| Track | Software control | External evidence still required |
|---|---|---|
| CV-001 | Intended use and excluded uses are represented and bounded | Approved protocol, population, inclusion/exclusion and scope decision |
| CV-002 | Owner/gate fields are required and typed | Named accountable owners, governance approval and escalation contacts |
| CV-003 | Privacy/security, consent/waiver and retention are explicit gates | Approved privacy, consent/waiver and data-retention evidence |
| CV-004 | Stop, incident, rollback and manual fallback are explicit gates | Approved safety protocol and executed fallback/incident drill |
| CV-005 | Backup/restore is a required prerequisite, not inferred from simulation | Recovery/DR evidence and approved destination/retention |
| CV-006 | Device qualification is a required external gate | Real device/host/clock/network/power/recovery qualification |
| CV-007 | Auth/transport and HIS integration are separate required gates | Real IdP/mTLS and HIS acknowledgment/integration evidence |
| CV-008 | Training and human-factors requirements are explicit | Staff walkthrough, wording review, alarm-fatigue review and no-treatment-order interpretation |
| CV-009 | Independent review and analysis semantics are required | Independent adjudication owner, analysis plan, coverage and denominator evidence |
| CV-010 | Decision gate prevents automatic promotion to treatment workflow | Signed continue/modify/pause/reject governance decision |

## Hardening controls

The runtime preflight now rejects unsafe owner/reference strings, raw identity/contact/secret markers, non-boolean gate values, empty or wrongly typed excluded-use lists, self-asserted external evidence classes and any `real_world_authorization` value other than literal `False`. The preflight response hardcodes the no-authorization boundary and returns copied lists/dictionaries so caller mutation cannot alter the next result.

The machine-readable readiness manifest keeps all 10 tracks at `SOFTWARE_PREFLIGHT_EXTERNAL_PENDING`, requires independent verification, keeps execution `NOT_STARTED`, and fixes the claim boundary to `NO_CLINICAL_VALIDATION_OR_ACCURACY_CLAIM`. Analysis semantics require review coverage, explicit denominators, visible unreviewed events and a ban on treating synthetic/replay data as clinical evidence.

## Verification boundary

The phase-end suite runs the existing P1-006 preflight regression and the new adversarial suite. It mutates status, execution, clinical validation, real-world authorization, evidence class, clinical claim, dependency, tracks, hard stops, opaque references, analysis semantics, owner types, gate types and preflight output objects. It also validates the template/schema, scans runtime/readiness artifacts for private-key markers and runs `git diff --check`.

All results are **software verification**. They do not establish clinical accuracy, sensitivity, specificity, PPV, NPV, clinical effectiveness, patient outcomes, regulatory compliance, real-world safety or authorization to test with patients.

## External prerequisites and hard stops

Before any real-world clinical validation, the project still needs clinical governance approval, a named clinical owner, approved protocol and population, consent/waiver decision, privacy/security review, retention/deletion decision, staff training, stop/incident/rollback/manual fallback path, backup/restore evidence, device and host qualification, real OIDC/mTLS and HIS validation, independent review, analysis plan and a signed change/decision gate. Any unresolved privacy leakage, security incident, identity mismatch, missing fallback, missing retention decision, serious missed event or operator interpretation of a signal as treatment requires a stop.
