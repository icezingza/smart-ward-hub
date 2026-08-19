# Smart Ward Hub — Device Trust Baseline Report

**Release status:** P0-hardened software baseline with Device Trust signed-telemetry and lifecycle baseline  
**Deployment status:** pilot deployment configuration pending  
**Clinical status:** clinical validation pending

## 1. Executive summary

This release adds a separate **Device Trust & Secure Provisioning** software layer without replacing the existing `TelemetryPacket v1`, Zero-PII model, EdgeTelemetryStore, SQLite WAL source of truth, or scope-based operator authentication. The design preserves the current API body contract and carries the device-authentication envelope through HTTP headers so the telemetry payload remains versioned and interoperable.

The implemented baseline uses Ed25519 public-key credentials, canonical packet serialization, signed telemetry verification in `enforce` mode, `observe` mode for shadow deployment, credential lifecycle states, audit events, and the existing monotonic sequence replay guard. It does not yet implement manufacturer CA verification, secure-element/HSM key custody, factory private-key operations, geofence enforcement, or external WORM anchoring.

The correct claim is therefore:

> **Canonical signed telemetry and device-credential lifecycle controls are functionally verified in software; manufacturer provisioning, hardware key custody, network validation and clinical validation remain pending.**

## 2. Trust boundary and request contract

The `TelemetryPacket v1` JSON body remains unchanged. In `enforce` mode, the request additionally requires:

| Header | Meaning |
|---|---|
| `X-Device-Key-ID` | Public-key credential identifier enrolled for the device |
| `X-Device-Signature` | URL-safe base64 Ed25519 signature over canonical packet bytes |

The signed canonical message covers the complete Pydantic packet representation, including `schema_version`, `device_id`, `sequence`, `timestamp`, `ppg`, `accel_x`, `accel_y`, `accel_z`, `skin_temp`, `battery_pct`, `heart_rate` and `spo2`. A mutation to a signed field therefore invalidates the signature before the packet can enter the telemetry buffer.

The device trust boundary is separate from patient pairing. Enrollment verifies and stores only public-key material and lifecycle metadata. Patient pairing remains an authenticated operator action binding `patient_token`, `bed_no` and `device_id`. No device private key, factory master secret or device seed map is stored by this implementation.

## 3. Runtime modes

| Mode | Behavior | Intended use |
|---|---|---|
| `disabled` | Legacy behavior; no signed envelope required | Existing local regression and compatibility checks |
| `observe` | Missing or invalid signature is audited as unverified but telemetry continues | Shadow mode and staged pilot onboarding |
| `enforce` | Missing, invalid, expired, suspended or revoked credential returns HTTP 401 | Controlled deployment after provisioning and hardware gates |

`SW_DEVICE_TRUST_MODE` defaults to `disabled` for compatibility. The pilot template recommends `observe` until real device provisioning, clock behavior and operator procedures are validated. `SW_DEVICE_TRUST_CLOCK_SKEW_SECONDS` defaults to 30 seconds and must be calibrated against device clock quality and the ward network.

## 4. Credential lifecycle

The new `device_credentials` table stores `device_id`, unique `key_id`, algorithm, public key, optional certificate fingerprint metadata, status and lifecycle timestamps. Private keys are intentionally absent. Enrollment of a new active key suspends a previous active credential for the same device. The lifecycle endpoint supports `ACTIVE`, `SUSPENDED` and `REVOKED`; revoked keys cannot be reactivated.

This is a software lifecycle baseline, not a complete manufacturing PKI. A production factory flow still needs an independently managed manufacturer CA, certificate chain validation, secure-element or HSM custody, rotation/revocation policy, dual control and hardware-in-loop evidence.

## 5. Implementation evidence

| Evidence | Result | Classification |
|---|---|---|
| Public-key enrollment and fingerprinting | Passed | Software functional evidence |
| Credential persistence across a new SQLAlchemy session | Passed | Persistence boundary evidence |
| Signed canonical `TelemetryPacket v1` accepted | Passed | Enforce-mode evidence |
| Signed-field mutation rejected | Passed | Integrity/mutation evidence |
| Missing signature rejected in enforce mode | Passed | Fail-closed mode evidence |
| Validly signed duplicate rejected by sequence guard | Passed | Combined authenticity and replay evidence |
| Revoked credential rejected | Passed | Lifecycle enforcement evidence |
| Unsigned packet accepted and audited in observe mode | Passed | Shadow-mode continuity evidence |
| Audit log contains no patient token | Passed | Zero-PII audit evidence |
| Alembic clean upgrade reaches `2c3d7e4f9a10` | Passed | Migration evidence |
| Full `run_all_tests.py` | Passed | Regression evidence |

The evidence above is software verification. It is not evidence of secure-element resistance, firmware correctness, RF security, anti-cloning protection, factory provenance, clinical effectiveness or regulatory compliance.

## 6. Safety constraints

Device Trust must be **fail-safe for patient monitoring**. An authentication, location or geofence anomaly should create an alert, audit event and controlled degraded-trust/quarantine state. It must not automatically brick a device or stop monitoring solely because of a transient network, clock or location signal. Any future enforcement that can interrupt monitoring requires clinical safety review and explicit rollback behavior.

## 7. Next external validation gates

| Gate | Required evidence |
|---|---|
| Manufacturer provisioning | Asymmetric CA chain, certificate enrollment, revocation and counterfeit-device rejection |
| Key custody | Secure element/HSM, extraction-resistance, rotation, dual control and recovery drill |
| Firmware interoperability | Canonical serialization and signature tests from real device firmware across languages |
| Clock and network behavior | Skew, offline buffering, reconnect, packet loss and delayed-delivery tests |
| Geofence/trust degradation | False-location, network-loss and patient-safety continuity scenarios |
| External evidence | Independent append-only/WORM anchor, trusted timestamp, retention and cross-boundary verification |
| Clinical governance | Shadow-mode review, false-positive/negative analysis, alarm-fatigue controls and sign-off |

## References

[1]: ./device_trust.py "Canonical Ed25519 device-trust verification"
[2]: ./test_device_trust.py "Device Trust enforce-mode regression"
[3]: ./test_device_trust_observe.py "Device Trust observe-mode regression"
[4]: ./alembic/versions/2c3d7e4f9a10_device_trust_credentials.py "Device Trust credential migration"
[5]: ./PRODUCT_DIFFERENTIATORS.md "Strategic product differentiators"


## 8. P1 key-custody contract extension

`key_custody_contract.py` and `test_key_custody_contract.py` add a software-only custody registry contract. It rejects private-key material, requires dual-control activation, records manufacturer/secure-element/non-exportability attestation flags, links rotations through `previous_key_id`, suspends the old key after a successful rotation, makes `REVOKED` terminal and turns a lost-device incident into a terminal `LOST`/revoked state. Registry snapshots contain public identity and lifecycle metadata only.

The software fixture may activate without hardware attestation only when explicitly configured with `allow_software_fixture=True`; those records are labelled `UNVERIFIED`. This supports deterministic contract testing and does not establish manufacturer CA provenance, HSM/secure-element protection, extraction resistance, firmware interoperability, MDM integration or independent revocation distribution.
