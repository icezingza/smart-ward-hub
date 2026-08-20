# P1-003 Device Trust Key-Custody Readiness Report

**Decision:** `KEY_CUSTODY_SOFTWARE_PREPARATION_READY`
**Key-custody execution:** `NOT_STARTED`
**Hardware custody validation:** `UNVERIFIED`
**Product status:** `NOT_PRODUCTION_READY`

## Scope

This package hardens the software contract for public-key provisioning and prepares seven key-custody tracks. It does not generate, import, escrow or verify production private keys; it does not attest a manufacturer CA, secure element, HSM, firmware, MDM or independent revocation service.

## Prepared tracks

| Track | Software preparation | External evidence still required |
|---|---|---|
| KT-001 | Unique device/key identity and Ed25519-only contract | Manufacturer provenance and anti-cloning evidence |
| KT-002 | Public fingerprint/lifecycle metadata only; private material rejected | Secure-element/HSM non-exportability and extraction resistance |
| KT-003 | Two distinct approver references required | Hospital IAM separation-of-duties transcript |
| KT-004 | CA/secure-element/non-exportable flags captured as explicit fields | Real manufacturer chain and hardware-in-loop attestation |
| KT-005 | Previous-key link and old-key suspension contract | Staged rollout, rollback and fleet coordination |
| KT-006 | Reasoned revocation and incident-bound lost-device terminal state | Independent distribution, MDM/asset process and recovery drill |
| KT-007 | Protected evidence/custody/read-back references required | Retention, independent read-back and external review |

## Hardening changes

The registry now rejects non-list approver inputs, non-string revocation reasons and non-string lost-device incident IDs. Mutating a returned provisioning record no longer mutates registry state. Rotation replay is rejected after the previous key is suspended; revoked/lost terminal states remain non-suspendable and non-reactivatable. The readiness manifest uses a copied authorization boundary so input mutation cannot change the global locked constant.

## Verification

The existing contract and negative tests plus the new adversarial suite pass. The phase-end gate runs all three suites, validates the blank-safe template/schema, checks `NOT_STARTED`/`UNVERIFIED`/`PENDING` status locks, scans for private-key blocks and runs `git diff --check`.

All results are **software verification**. `allow_software_fixture=True` remains explicitly `UNVERIFIED` and must not be described as hardware trust.

## Claim boundary

The valid claim is **Device Trust & Secure Provisioning software baseline with signed telemetry and lifecycle controls**. This package does not support `manufacturer-authenticated provisioning`, `secure-element/HSM protection`, `anti-cloning resistance`, `tamper-proof`, `clinical-ready` or `production-ready` claims.

The external gate remains blocked until Wave 0 owner appointment, signed scope/test window, custody ceremony, manufacturer evidence and independent verification are supplied.
