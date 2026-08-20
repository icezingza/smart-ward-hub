# Wave 1 External-Execution Readiness Report

**Prepared at:** `2026-08-20`
**Current repository revision at manifest generation:** `fc3ed3989a3507656903c25722d78e240cbf78c7`
**Environment:** local readiness only

## Decision

**`READY_FOR_OWNER_APPOINTMENT`**

The repository is internally coherent enough to begin external owner appointment and test-window preparation. It is **not ready for external execution**. The readiness validator found 15 required external prerequisites that are absent from the repository. No endpoint, IdP, certificate, manufacturer custody service, physical Acer fixture or clinical workflow was contacted.

## Readiness checks

| Check | Result |
|---|---|
| Repository HEAD matches `origin/main` | PASS |
| Release freeze status | PASS |
| Wave 1 local preflight evidence exists | PASS |
| No-authorization boundary | PASS |
| External execution | NOT_STARTED |
| Physical execution | NOT_STARTED |
| Evidence class | `SOFTWARE_VERIFIED/SIMULATION_ONLY` |

## Missing prerequisites

| Track | Required before execution |
|---|---|
| Wave 0 governance | signed scope, approved test window, named stop authority, rollback owner, independent verifier |
| GV-04 OIDC/mTLS | isolated non-production IdP/HIS tenant, certificate owner/chain/rotation-revocation plan, approved network ACL and deny transcript |
| GV-08 key custody | OEM or approved HSM/secure-element custody owner, dual-control ceremony, real revocation distribution/read-back |
| GV-06 Acer bench | dedicated Acer fixture, isolated USB-serial loopback fixture, exact operator confirmation `I_HAVE_A_NONPRODUCTION_LOOPBACK`, independent physical witness |

## Required gate behavior

The validator intentionally reports `READY_FOR_OWNER_APPOINTMENT` rather than `READY_FOR_EXTERNAL_EXECUTION`. External execution may begin only after the external coordinator records the missing prerequisites, signs the scope and test window, and provides the stop/rollback/custody identities. A local change must not bypass these checks.

The authorization boundary remains:

```text
external_authority=NONE
clinical_validation_authorized=false
production_authorized=false
runtime_authority=NONE
pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
```

## Evidence references

The machine-readable source is [`evals/micro_rag/evidence/wave1-external-execution-readiness-20260820.json`](./evals/micro_rag/evidence/wave1-external-execution-readiness-20260820.json). The validator is `wave1_external_execution_readiness.py` and its regression is `test_wave1_external_execution_readiness.py`.
