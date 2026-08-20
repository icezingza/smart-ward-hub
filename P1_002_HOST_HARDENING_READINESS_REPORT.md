# P1-002 Host Hardening Readiness Report

**Decision:** `SOFTWARE_PREPARATION_READY`
**Host execution:** `NOT_STARTED`
**Physical validation:** `UNVERIFIED`
**Clinical validation:** `PENDING`
**Product status:** `NOT_PRODUCTION_READY`

## Scope

This package prepares the software-side contract for the Acer Spin N17H2 Fixed Hub candidate. It validates safe configuration defaults, source/runtime separation, loopback reference behavior, no embedded credentials, stop rules and evidence placeholders. It does not execute or attest to Windows accounts, ACLs, disk encryption, firewall state, patch state, Task Scheduler, time synchronization, kiosk controls, thermal/power behavior or production network exposure.

## Prepared controls

| Control group | Software preparation | External evidence still required |
|---|---|---|
| Least privilege | Dedicated non-admin service identity is required by contract | Windows account/group transcript and access review |
| Data/runtime boundary | Database, checkpoint and logs must remain outside source tree | Target-host path and ACL transcript |
| Network exposure | Loopback-only reference and explicit non-wildcard host policy | Firewall export, listener/port scan and approved gateway ACL |
| Pilot defaults | Docs disabled, no auto-create DB, no seed data | Redacted target-host readiness transcript |
| Identity transport | OIDC selected; static tokens limited to bench/development | Real IdP/mTLS, certificate lifecycle and secret-store evidence |
| Recovery | Start/stop/restart/rollback and strict backup/restore are required | Task Scheduler/supervisor failure drill and target-host restore |
| Privacy/monitoring | Kiosk/privacy and health/disk/backup/auth/sync observables are required | Site survey, human-factors review and owned alert transcript |

## Fail-closed contract

`p1_002_host_hardening_readiness.py` rejects unknown fields, source/runtime state mutations, production/clinical status changes, non-opaque evidence references, raw contact data, secret markers, incomplete control sets and changes to the locked authorization boundary. All controls remain either `SOFTWARE_PASS` for local safe defaults or `SOFTWARE_PASS_EXTERNAL_PENDING` when target-host/external evidence is required.

The machine-readable template and schema are blank-safe. They contain no real account, endpoint, token, certificate, private key, patient data or host credential. External owners must populate evidence references only after appointment, signed scope, approved test window, stop authority and rollback reference exist.

## Verification

`test_p1_002_host_hardening_readiness.py` returned `P1_002_HOST_HARDENING_READINESS_TESTS_PASSED`. The regression covers template validity, unknown fields, authorization mutation, host execution mutation, control-set deletion, raw identity/secret rejection and opaque evidence-reference enforcement. This is software-preparation evidence only.

## Claim boundary

> Completing this template or passing local validation does not establish a hardened Acer host, encrypted volume, firewall enforcement, real least-privilege account, production service recovery, clinical readiness or production readiness.

The valid local product claims remain **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation** and **clinical validation pending**.
