# Wave 4 Independent Review Evidence Mapping

**Date:** 2026-08-21

**Package state:** `READY_FOR_EXTERNAL_OWNER_APPOINTMENT`

**Evidence class:** `SOFTWARE_COORDINATION_ONLY`

**Decision boundary:** This mapping is a local index for independent review preparation. It is not an external evidence bundle, not an external decision and not an authorization record.

## Mapping matrix

| Test case | Review focus | Local software evidence | Evidence class | External verification still required |
|---|---|---|---|---|
| T-01 | Approved endpoint identity | Wave 1 technical readiness, identity/transport preparation | `SOFTWARE_PREPARATION_ONLY` | Non-production endpoint identity, certificate/service transcript and owner read-back |
| T-02 | OIDC issuer, audience and JWKS | Wave 1 software-preparation validator and config template | `SOFTWARE_PREPARATION_ONLY` | Real test tenant, issuer/audience/JWKS and invalid-token transcript |
| T-03 | mTLS lifecycle | Wave 1 technical validation package, P0 mTLS configuration tests | `SOFTWARE_SIMULATION_ONLY` | Test CA, handshake, renewal, revocation and external custody transcript |
| T-04 | ACL and segmentation | P1-002 host readiness and host hardening checklist | `SOFTWARE_PREPARATION_ONLY` | Acer firewall/port export, allow/deny route evidence and owner sign-off |
| T-05 | Contract/version negotiation | Wave E evidence contract, strict schema and existing simulator regression | `SOFTWARE_VERIFIED_SIMULATION_ONLY` | External API version, compatibility and rollback evidence |
| T-06 | Freeze/scope/governance binding | Release freeze manifest, Wave 0 governance checklist and Wave 3 package | `SOFTWARE_COORDINATION_ONLY` | Signed scope/window/expiry, external owner appointment and independent read-back |
| T-07 | Idempotency and uncertain commit | External authorization simulator and Wave E contract tests | `SOFTWARE_VERIFIED_SIMULATION_ONLY` | Real network timeout/commit reconciliation transcript |
| T-08 | Expiry and revocation | Device trust/key custody and external-anchor readiness contracts | `SOFTWARE_PREPARATION_ONLY` | External certificate/key revocation propagation and stale-cache read-back |
| T-09 | Response authenticity | Wave 2 forensic/anchor boundary and Wave E signed-response schema | `SOFTWARE_SIMULATION_ONLY` | External signature, key ID, trust chain and independent verification |
| T-10 | Audit and custody | Backup/restore contract, FileAnchorStore and Wave 2 local-anchor separation | `SOFTWARE_VERIFIED_LOCAL_ONLY` | Independent WORM/append-only custody, trusted timestamp and restore/read-back |
| T-11 | Retry and rate limiting | Network pressure simulation and external authorization simulator | `SOFTWARE_SIMULATION_ONLY` | External quota/429/timeout transcript and approved retry policy |
| T-12 | Stop and recovery | P1-008 independent review operations, Wave 3 clinical/host stop rules and controlled-pilot gate | `SOFTWARE_COORDINATION_ONLY` | Named stop authority, recovery approver, incident channel and signed drill |

## Common index rules

Every indexed artifact must have a new evidence ID, gate/test-case binding, evidence class, SHA-256, source revision, timezone-aware preparation timestamp, `prepared_by_role`, `redaction=PASS`, chain-of-custody reference and independent read-back status. A local record may use a pending read-back reference but must not call that reference external custody or signed authorization.

The consolidated index must contain exactly one mapping entry for each T-01 through T-12. The index may contain multiple local artifact references per test case, but it must never synthesize a missing external transcript or convert a local simulation into `READY_FOR_INDEPENDENT_REVIEW` evidence.

## Locked boundary

```text
external_authority=NONE
clinical_validation_authorized=false
production_authorized=false
runtime_authority=NONE
pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
```

The independent reviewer must verify the freeze hash, source revision, artifact hashes, redaction, role separation, scope/expiry/rollback, failure/blocked cases and residual risk. Only an external reviewer and authorized external authority can issue a signed decision; the local index and simulator cannot create that decision.

## References

[1]: `file:///home/ubuntu/smart-ward-hub-reconcile/PRODUCTION_READINESS_ROADMAP_20260820.md` "Production Readiness Roadmap"

[2]: `file:///home/ubuntu/smart-ward-hub-reconcile/EXTERNAL_AUTHORIZATION_API_WAVE_E_EXTERNAL_VALIDATION_DOSSIER.md` "Wave E External Validation Dossier"

[3]: `file:///home/ubuntu/smart-ward-hub-reconcile/GV10_INDEPENDENT_REVIEW_DOSSIER.md` "GV-10 Independent Review Dossier"
