# Wave 1 Local Preflight Report

**Prepared at:** `2026-08-20T12:00:03Z`
**Current repository revision:** `f2f9bf0280928248dde93d2d85d667b56ba142d7`
**Release-freeze source revision:** `0da6a381e4004ea31537383a351bce9846418ec1`
**Environment:** local software/non-production preflight only

## Decision

**`WAVE_1_LOCAL_PREFLIGHT_PASS_EXTERNAL_EXECUTION_BLOCKED`**

Local contract and dry-run checks pass. External execution remains blocked because no real IdP/HIS endpoint, certificate owner, manufacturer key-custody service, enumerated Acer COM port, isolated physical loopback fixture or external owner approval is present.

The no-authorization boundary remains:

```text
external_authority=NONE
clinical_validation_authorized=false
production_authorized=false
runtime_authority=NONE
pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
```

## Test results

| Track | Test | Result | Evidence class | Limitation |
|---|---|---|---|---|
| GV-04 | `test_p0_oidc_config.py` | PASS | `SOFTWARE_VERIFIED` | validates configuration shape/fail-closed behavior; no live IdP |
| GV-04 | `test_p0_mtls_config.py` | PASS | `SOFTWARE_VERIFIED` | validates local file hygiene/fail-closed behavior; no real handshake |
| GV-08 | `test_key_custody_contract.py` | PASS | `SOFTWARE_VERIFIED` | registry/fixture lifecycle only; no manufacturer custody |
| GV-08 | `test_key_custody_contract_negative.py` | PASS | `SOFTWARE_VERIFIED` | negative contract cases only |
| GV-04/GV-05 | `test_auth_fail_closed.py` and `test_deployment_readiness.py` | PASS | `SOFTWARE_VERIFIED` | synthetic environment; no target host/IdP |
| GV-06 | `serial_bench_runner.py --list-ports` | PASS with blocker | software observation | `pyserial_unavailable`; `ports=[]` |
| GV-06 | `serial_bench_runner.py --dry-run` | PASS with blocker | `SOFTWARE_VERIFIED` | `DRY_RUN_ONLY`; codec passes; physical validation pending |
| GV-06 | `test_serial_framing.py` | PASS | `SOFTWARE_VERIFIED` | no physical transport |
| GV-06 | `test_serial_bench_runner.py` | PASS | `SOFTWARE_VERIFIED` | validates physical-path safety only |

## Interpretation by gate

### GV-04 — OIDC/mTLS

The local configuration and fail-closed contracts are verified. There is no evidence yet for real discovery/JWKS, issuer/audience claims, mTLS handshake, certificate chain, rotation/revocation or network ACL segmentation. GV-04 remains `UNVERIFIED`.

### GV-08 — Device Trust/key custody

Software lifecycle controls and negative cases pass. The repository still has no manufacturer provenance, secure-element/HSM non-exportability, dual-control ceremony, real key rotation or independent revocation distribution. GV-08 remains `UNVERIFIED`.

### GV-06 — Acer/serial/power-loss

The dry-run intentionally did not open a port and reported `pyserial_unavailable` with no enumerated ports. Framing tests pass as software evidence only. Physical S-001–S-015, power interruption, disk-full and target-host recovery evidence are absent. GV-06 remains `BLOCKED`.

## Required next action

An external coordinator must first appoint the Wave 0 roles and sign the scope, test window, stop authority and rollback package. After that, the security owner may open an isolated OIDC/mTLS test tenant, the custody owner may conduct a non-production key ceremony, and the reliability owner may execute the Acer bench procedure only with the exact confirmation phrase `I_HAVE_A_NONPRODUCTION_LOOPBACK`.

No test in this report used patient data, production credentials, production network, real private keys, physical hardware or clinical workflow. The report is local software/dry-run evidence and cannot close any external gate.

## Evidence file

Machine-readable evidence is stored at [`evals/micro_rag/evidence/wave1-preflight-20260820.json`](./evals/micro_rag/evidence/wave1-preflight-20260820.json).
