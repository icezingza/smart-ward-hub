# Wave 1 Technical Foundation — Readiness Report

**Report date:** 2026-08-21

**Decision:** `READY_FOR_OWNER_APPOINTMENT`

**Execution status:** `NOT_STARTED`

**Environment:** `ISOLATED_NON_PRODUCTION_ONLY`

**Product status:** `NOT_PRODUCTION_READY`

## 1. Scope and evidence boundary

Wave 1 prepares three technical foundations: **GV-04 identity/transport**, **GV-08 Device Trust and key custody**, and **GV-06 Acer serial/power/recovery bench**. The package is a software-preparation contract and does not contact a real IdP, HIS, certificate authority, manufacturer custody service, HSM, secure element, Acer COM port, physical fixture, patient device or clinical workflow.

The correct interpretation is **software verification and deterministic simulation evidence only**. Passing local validators or serial framing tests does not establish real OIDC/mTLS trust, manufacturer hardware provenance, secure-element custody, physical serial capability, power-loss resilience or clinical readiness.

## 2. Hardened contract

`wave1_software_preparation.py` now enforces exact top-level and nested field sets, strict three-track membership, immutable track definitions, blank-safe template completeness, caller-mutation isolation, lowercase freeze SHA-256, opaque appointment/matrix/scope/window/rollback references, controlled non-production text, raw identity/contact and secret rejection, track status `PREPARED_SOFTWARE_ONLY`, execution status `NOT_STARTED`, and `hardware_or_external_validation=UNVERIFIED`.

The three tracks remain fixed as follows:

| Track | Gate | Software state | External state |
|---|---|---|---|
| `oidc_mtls` | GV-04 | `PREPARED_SOFTWARE_ONLY` | Owner/tenant/certificate/ACL evidence pending |
| `key_custody` | GV-08 | `PREPARED_SOFTWARE_ONLY` | OEM/HSM/secure-element/custody evidence pending |
| `acer_bench` | GV-06 | `PREPARED_SOFTWARE_ONLY` | Acer fixture/COM/physical-witness evidence pending |

## 3. Verification evidence

| Verification | Result | Evidence |
|---|---|---|
| Existing Wave 1 software-preparation regression | Passed | `test_wave1_software_preparation.py` |
| Wave 1 adversarial/failure-injection suite | Passed | `test_wave1_software_preparation_hardening.py` |
| External-execution readiness regression | Passed | `test_wave1_external_execution_readiness.py` |
| Wave 1 phase-end hardening gate | Passed | `test_wave1_software_preparation_phase_end_hardening.py` |
| Template/schema validation | Passed | Phase-end gate |
| GV-04/GV-08/GV-06 coverage | Passed | Phase-end gate |
| Private-key marker scan | Passed | Phase-end gate |
| `git diff --check` | Passed | Phase-end gate |
| Master regression integration | Registered | `run_all_tests.py`; final result follows commit/freeze refresh |

The external-execution readiness artifact still reports `READY_FOR_OWNER_APPOINTMENT` with 15 missing external prerequisites. It does not report `READY_FOR_EXTERNAL_EXECUTION`, `EVIDENCE_SUBMITTED`, `PASSED` or `AUTHORIZED_BY_EXTERNAL_OWNER`.

## 4. Locked authorization boundary

```text
external_authority=NONE
clinical_validation_authorized=false
production_authorized=false
runtime_authority=NONE
pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
```

The Wave 1 package cannot change this boundary. The software-preparation and local-preflight results do not authorize execution.

## 5. External prerequisites and stop rules

Before any isolated external activity, Wave 0 must provide signed scope, approved timezone-aware window and allowlist, named stop authority, rollback owner, independent verifier and custody references. GV-04 additionally requires a non-production IdP/HIS tenant, certificate chain and rotation/revocation plan, approved ACL and deny transcript. GV-08 requires manufacturer or approved HSM/secure-element custody, dual-control ceremony, public-key/device inventory, revocation distribution/read-back and lost-device handling. GV-06 requires a dedicated Acer Spin N17H2 fixture, isolated USB-serial loopback, exact operator phrase `I_HAVE_A_NONPRODUCTION_LOOPBACK`, independent physical witness and no-production-network attestation.

If the Acer host has no enumerated COM port, GV-06 remains blocked. A software framing harness, synthetic packet run or dry-run serial runner cannot be substituted for physical evidence. No production credentials, raw patient data, private keys, bearer tokens, raw serial frames or production endpoint secrets may enter the repository or evidence directory.

## 6. Final claim boundary

This package supports the claims **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation**, **clinical validation pending**, and **pilot deployment configuration pending**. It does not support the claims **clinical-ready**, **production-ready**, **tamper-proof**, or complete HIPAA/PDPA compliance based on software tests alone.
