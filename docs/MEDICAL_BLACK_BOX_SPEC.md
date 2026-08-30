# Medical Black Box and Tamper-Evident Forensic Vault

## Evaluation target

This slice is for hospital IT, security and clinical-governance evaluation in an isolated lab. It demonstrates bounded incident capture, SHA-256 chain verification and optional RSA signatures over synthetic or approved bench telemetry. It is not legal advice, clinical validation, ISO certification or a guarantee of admissibility.

## Data model

Each `ForensicPackage` contains the alert/session/device/bed scope, an opaque patient token, the selected telemetry samples, the previous block hash, the current SHA-256 block hash and optional signature metadata. Private keys never enter the database, logs, API response or repository.

The chain contract is:

```text
block_hash_n = SHA-256(previous_hash + ":" + canonical_frozen_payload_n)
```

The optional signature contract is RSA-PSS with SHA-256 over the 32-byte block hash. Keys smaller than 2048 bits are rejected.

## Capture and freeze rules

- `EdgeTelemetryStore` remains a bounded per-device in-memory ring buffer.
- Incident freeze selects samples by `received_at` from the configured recent window, default 600 seconds.
- The oldest boundary sample at exactly 600 seconds is included; older samples are excluded.
- The sample-count bound must be sized for the approved device sample rate. The default `90000` samples covers 600 seconds only at rates up to 150 accepted packets/second per device.
- An alert automatically freezes the selected window. Manual session freeze requires an unresolved alert and is idempotent.
- Missing signing configuration produces an explicit `UNSIGNED` package. `SW_FORENSIC_SIGNING_REQUIRED=true` fails startup unless a key path is configured.
- Verification checks chain order and block hashes before signatures. Invalid signatures fail integrity verification.
- A signature whose trusted key is unavailable or whose fingerprint differs is reported as unverified, not valid.

## Configuration

```text
SW_FORENSIC_WINDOW_SECONDS=600
SW_FORENSIC_SIGNING_PRIVATE_KEY_PATH=/run/secrets/forensic-signing-key.pem
SW_FORENSIC_SIGNING_REQUIRED=true
```

The PEM key must be provisioned outside source control. Production key custody should use an HSM/KMS or equivalent controlled signing service rather than a long-lived plaintext file.

## Acceptance gates

- deterministic 600-second window boundary test passes;
- SHA-256 previous-block chaining detects payload or order changes;
- RSA-2048 PSS signature verifies and rejects a changed hash/signature;
- FastAPI alert flow creates a signed package when a test key is configured;
- unsigned packages are never reported as signed or externally verified;
- package and audit outputs contain no private-key material;
- Alembic migration upgrades and downgrades the signature metadata safely;
- master regression and release-freeze integrity checks pass.

## Explicit production and legal gaps

- The current buffer stores accepted `TelemetryPacket v1` samples, not a vendor-verified raw high-frequency waveform.
- RAM data can be lost on power failure before freeze; durable pre-event journaling requires a separate approved design.
- Local SQLite rows and a local anchor are tamper-evident software evidence, not immutable WORM storage.
- Key generation, custody, rotation, revocation, trusted timestamps, certificate chain and independent verification are not established by this module.
- ISO/IEC 27037 describes handling activities for potential digital evidence; this implementation has not been independently assessed or certified against it.
- Court admissibility depends on jurisdiction, collection procedure, provenance, chain of custody, expert testimony and judicial evaluation. Software signatures alone cannot guarantee immediate admissibility.
