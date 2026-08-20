# Wave 1 External Evidence Preparation Matrix

**Prepared:** 2026-08-21

**Scope:** GV-04 identity/transport, GV-08 Device Trust/key custody and GV-06 Acer bench foundation.

**Current decision:** `READY_FOR_OWNER_APPOINTMENT`

**Execution:** `NOT_STARTED`

**Evidence class:** `SOFTWARE_VERIFIED/SIMULATION_ONLY` until external records are submitted and independently verified.

## Executive conclusion

The current machine-readable readiness record lists **15 missing external prerequisites**. All 15 are external inputs; none can be legitimately manufactured by local software tests. The repository is prepared to receive opaque references, signed scope, test-window approvals and redacted evidence, but it has not appointed external owners, opened a real IdP/HIS or network path, verified manufacturer custody, or performed a physical Acer bench run.

> The correct next state is owner appointment and evidence intake, not external execution. The authorization boundary remains `external_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false`, `runtime_authority=NONE`, and `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.[1] [2]

## Evidence preparation matrix

| # | Missing prerequisite | Track / gate | Required external owner | Preparation path | Minimum acceptance evidence | Stop condition | Current status |
|---:|---|---|---|---|---|---|---|
| 1 | `wave0_signed_scope` | Wave 0 governance | External coordinator + clinical owner | Populate Wave 0 intake with opaque `scope_id`, signed-scope ref, approved-by ref, explicit in/out-of-scope, data boundary and purpose. | Signed scope hash, signer/role refs, redaction PASS, independent read-back. | Scope is unsigned, ambiguous, exceeds non-production scope or includes patient/production data. | `MISSING_EXTERNAL` |
| 2 | `wave0_approved_test_window` | Wave 0 governance | External coordinator + stop authority | Define a timezone-aware start/end window, expiry, allowlist and test environment before any external call. | Approval ref, UTC-normalized timestamps, allowlist ref and expiry evidence. | Naive/expired window, missing allowlist or window outside signed scope. | `MISSING_EXTERNAL` |
| 3 | `wave0_named_stop_authority` | Wave 0 governance | Stop authority | Record an opaque actor/org appointment, stop rules and notification route. | Appointment ref, stop-rule ref and notification/read-back ref. | No named stop authority or notification path; any clinical/privacy/security stop request is ignored. | `MISSING_EXTERNAL` |
| 4 | `wave0_rollback_owner` | Wave 0 governance | Rollback owner | Bind a target revision to a restore/rollback drill and owner approval. | Target revision ref, approval ref, restore-drill evidence and RPO/RTO decision. | Unknown revision, failed restore, no owner approval or ambiguous rollback target. | `MISSING_EXTERNAL` |
| 5 | `wave0_independent_verifier` | Wave 0 governance | Independent verifier | Appoint a verifier separate from coordinator and execution roles; define read-back channel. | Appointment ref, verification channel and signed/read-back package result. | Role collision, no independent channel or unverifiable evidence package. | `MISSING_EXTERNAL` |
| 6 | `gv04_nonproduction_idp` | GV-04 identity/transport | Security owner + IdP owner | Provision an isolated non-production IdP/HIS tenant with test identities and no production trust. | Redacted issuer/discovery/JWKS response hash, tenant scope, test identity refs and timestamp. | Production tenant/credential, issuer or TLS host mismatch, untrusted response. | `MISSING_EXTERNAL` |
| 7 | `gv04_certificate_owner` | GV-04 identity/transport | Certificate owner / security owner | Establish non-production client/server certificate chain and rotation/revocation plan without storing private keys. | Redacted certificate fingerprints, chain metadata, rotation/revocation/rollback transcript. | Private key leakage, chain/hostname/clock failure or revoked certificate still accepted. | `MISSING_EXTERNAL` |
| 8 | `gv04_network_acl` | GV-04 identity/transport | Network/security owner | Approve isolated source/destination/port allowlist and test deny paths. | ACL approval ref, allow transcript and deny transcript from outside the allowlist. | Unexpected route, unauthorized endpoint reachability or missing deny evidence. | `MISSING_EXTERNAL` |
| 9 | `gv08_custody_owner` | GV-08 Device Trust/key custody | Custody owner + OEM/HSM/secure-element owner | Identify the manufacturer CA or approved custody boundary and custody responsibilities. | Opaque custody appointment, manufacturer/HSM boundary, device/key provenance ref. | Unverified device identity, unsupported hardware root or custody boundary unclear. | `MISSING_EXTERNAL` |
| 10 | `gv08_dual_control_ceremony` | GV-08 Device Trust/key custody | Custody owner + second approver + independent verifier | Schedule a dual-control non-production key issuance ceremony with no private-key export. | Ceremony record, two distinct approver refs, public-key fingerprint and read-back. | Single-person approval, private key export or missing independent read-back. | `MISSING_EXTERNAL` |
| 11 | `gv08_revocation_distribution` | GV-08 Device Trust/key custody | Custody/security owner | Rehearse key rotation, revocation/lost-device propagation and offline read-back. | Revocation incident ref, propagation transcript, terminal state and recovery/manual fallback result. | Revoked/lost key reactivated or propagation cannot be independently verified. | `MISSING_EXTERNAL` |
| 12 | `gv06_acer_fixture` | GV-06 Acer bench/recovery | Reliability owner + Acer host operator | Assign a dedicated Acer Spin N17H2 non-production fixture and record model/OS/driver/time source. | Fixture identity, driver/version evidence, host hardening and isolation attestation. | Shared/production host, unknown driver, unsafe network exposure or host identity mismatch. | `MISSING_EXTERNAL` |
| 13 | `gv06_loopback_fixture` | GV-06 Acer bench/recovery | Reliability owner + physical fixture owner | Prepare an isolated USB-serial loopback with exact serial parameters and exclusive access. | Fixture/adapter identity, port parameters, isolation evidence and S-001–S-015 test window. | No COM port, wrong framing parameters, shared port or non-isolated fixture. | `MISSING_EXTERNAL` |
| 14 | `gv06_operator_confirmation` | GV-06 Acer bench/recovery | Reliability owner / operator | Obtain the exact non-production confirmation `I_HAVE_A_NONPRODUCTION_LOOPBACK` immediately before a physical run. | Recorded operator attestation bound to test window and fixture, without personal data. | Missing or altered phrase, production target, live patient/device or unapproved network. | `MISSING_EXTERNAL` |
| 15 | `gv06_physical_witness` | GV-06 Acer bench/recovery | Independent physical bench witness | Appoint a witness separate from the operator and capture read-back of fixture, power/recovery and S-001–S-015 results. | Witness appointment, signed/read-back bench record, power/thermal/soak and recovery evidence. | No witness, failed power/recovery, missing COM enumeration or simulation substituted for physical evidence. | `MISSING_EXTERNAL` |

## Submission sequence

The recommended sequence is to complete Wave 0 role appointments and signed scope first, then approve a non-production test window and stop/rollback controls. GV-04, GV-08 and GV-06 should be executed independently in isolated environments, each with a separate evidence manifest, redaction result, source revision, hash/read-back and independent verification. A blocked gate must be explicitly reopened before new evidence is submitted. Local templates may be populated only with opaque references; raw names, email addresses, phone numbers, HN/AN/MRN/National ID, private keys, bearer tokens and production endpoint secrets are prohibited.[1] [2]

## Evidence status interpretation

| Status | Meaning |
|---|---|
| `SOFTWARE_PREPARATION_READY` | The repository contract and local validation are prepared. It is not external evidence. |
| `READY_FOR_OWNER_APPOINTMENT` | External roles and evidence intake may be coordinated. It is not permission to run tests. |
| `READY_FOR_EXTERNAL_EXECUTION` | Requires all prerequisites, approvals, custody/read-back and independent verification; not achieved. |
| `EVIDENCE_SUBMITTED` / `PASSED` | Requires external records and decision authority; no such local claim is made. |
| `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION` | Current pilot/clinical/production stop state. |

## References

[1]: `file:///home/ubuntu/smart-ward-hub-reconcile/evals/micro_rag/evidence/wave1-external-execution-readiness-20260820.json` "Wave 1 external-execution readiness manifest"

[2]: `file:///home/ubuntu/smart-ward-hub-reconcile/WAVE_1_TECHNICAL_VALIDATION_PACKAGE_20260820.md` "Wave 1 Technical Validation Package"

[3]: `file:///home/ubuntu/smart-ward-hub-reconcile/WAVE_0_EXTERNAL_OWNER_APPOINTMENT_PACKAGE_20260820.md` "Wave 0 External Owner Appointment Package"
