# Smart Ward Hub — Device Trust Key Custody and Provisioning Contract

**Status:** Software contract baseline implemented; manufacturer provisioning and hardware custody pending

## Purpose

This contract defines the lifecycle boundary for Device Trust public-key credentials without allowing private keys into Smart Ward Hub source code, database records, logs or registry snapshots. The Fixed Hub stores public-key identity and lifecycle metadata; a manufacturer CA, secure element, HSM or approved custody service must own private-key generation and protection in a real deployment.

## Provisioning lifecycle

```text
REQUESTED → PROVISIONING → ACTIVE → SUSPENDED
                              ├→ REVOKED
                              └→ LOST → REVOKED
```

A rotation creates a new key with a `previous_key_id` link. Activation requires dual-control approval. After the new key is active, the previous active key is suspended. Revoked or lost credentials are terminal and cannot be reactivated.

| Control | Software contract | External evidence still required |
|---|---|---|
| Stable identity | `device_id` and unique `key_id` | Manufacturer identity and anti-cloning provenance |
| Algorithm | Ed25519 only in current baseline | Firmware interoperability and approved algorithm policy |
| Material boundary | Public-key fingerprint only; private material rejected | Secure element/HSM non-exportability and extraction resistance |
| Activation | Dual-control approver IDs required | Separation of duties and operator identity in hospital IAM |
| Attestation | Manufacturer CA, secure element and non-exportable flags captured | Real CA chain, attestation protocol and hardware-in-loop evidence |
| Rotation | New key links to previous key; old key suspended | Staged firmware rollout, rollback and fleet coordination |
| Revocation | Reason required; status becomes terminal | Independent revocation distribution and offline behavior |
| Lost device | Incident ID required; credential becomes `LOST` and revoked | MDM/asset process, replacement and recovery drill |
| Evidence | Registry snapshot excludes private-key values | Protected audit sink, retention and independent review |

## Safe software fixture mode

The current `key_custody_contract.py` permits a test fixture to activate without hardware attestation only when `allow_software_fixture=True`. Such records are labelled `evidence_status=UNVERIFIED`. This mode exists for deterministic contract tests and must not be interpreted as manufacturer or hardware trust.

## Non-negotiable rules

The project must not import factory master secrets, device seed maps, private-key files or shared fleet secrets into source control. The Hub must not generate or escrow production private keys in its application database. A key with status `REVOKED` or `LOST` must not be reactivated. Any automatic enforcement that could stop patient monitoring requires a fail-safe degraded-trust policy, clinical safety review and rollback path.

## Claim boundary

The current claim is **Device Trust & Secure Provisioning software baseline with signed telemetry and lifecycle controls**. It is not evidence of manufacturer-authenticated provisioning, secure-element/HSM protection, anti-cloning resistance, tamper-proof evidence or production hardware security.
