# P1-003 — Key-Custody Test Review

**Review target:** `test_key_custody_contract.py`
**Implementation target:** `key_custody_contract.py`
**Review classification:** software contract review; no HSM, secure element, manufacturer CA or production IAM evidence

## What the existing test verifies

| Area | Lines | Result |
|---|---:|---|
| Initial state | 13–20 | New public-key record starts as `PROVISIONING` |
| Dual control | 21–31 | One approver cannot activate a credential |
| Software fixture boundary | 33–40 | Fixture activation is labelled `UNVERIFIED` |
| Rotation | 42–57 | New key links to old key and old key becomes `SUSPENDED` |
| Revocation | 59–67 | `REVOKED` credential cannot reactivate |
| Lost device | 69–79 | Incident ID produces terminal `LOST` state with revocation timestamp |
| Material boundary | 81–85 | Snapshot does not contain private-key value fields |

The test is deterministic, uses synthetic device identifiers and fingerprints, and does not call the FastAPI enrollment endpoint, the SQLAlchemy `DeviceCredential` table, real Ed25519 signing, a manufacturer CA, an HSM, a secure element or an independent revocation service.

## Review findings

| ID | Severity | Finding | Evidence | Remediation/status |
|---|---|---|---|---|
| KC-REV-001 | Medium | Attestation `evidence_id` was accepted but not validated for presence or persisted in the provisioning record, weakening traceability | `key_custody_contract.py` lines 16–21 and 97–117 | Add required evidence-ID validation and persist it; add negative/positive tests |
| KC-REV-002 | Low | Contract accepted whitespace-only `device_id`/`key_id` values because it checked truthiness but not trimmed content | `key_custody_contract.py` lines 74–79 | Reject blank-after-trim identifiers; add negative tests |
| KC-REV-003 | Low | Existing test did not exercise duplicate key IDs, invalid fingerprint shape, private-key argument rejection, or hardware-attestation fail-closed mode | Existing test lines 12–85 | Add focused negative-test matrix |
| KC-REV-004 | Medium | Existing test does not exercise the production API/database lifecycle or actual Ed25519 verification | `test_key_custody_contract.py` uses only in-memory registry | Keep as contract test and add/retain `test_device_trust.py` as API/crypto evidence; do not merge the evidence labels |
| KC-REV-005 | High residual | `evidence_status=VERIFIED` in the positive fixture represents flags supplied to the test, not independently verified hardware custody | Existing test lines 49–54 | Preserve label as software contract fixture; require external attestation transcript before any deployment claim |

## Additional test plan

The follow-up regression will cover: blank identifiers, malformed fingerprints, duplicate key IDs, private-key rejection, empty attestation IDs, invalid attestation objects, hardware-attestation fail-closed mode, duplicate approver collapse, blank revocation reason, blank lost-device incident, cross-device rotation rejection, rotation-link mismatch and immutable private-material boundary.

## Claim boundary

The correct conclusion remains: **Device Trust key-custody lifecycle controls are functionally verified in software**. This is not evidence of secure-element/HSM custody, manufacturer-authenticated provisioning, anti-cloning resistance, firmware interoperability, independent revocation distribution, regulatory compliance or clinical readiness.
