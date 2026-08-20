# Wave 1 Software Preparation Package

**Package state:** `SOFTWARE_PREPARATION_READY`
**Execution status:** `NOT_STARTED`
**Environment:** `ISOLATED_NON_PRODUCTION_ONLY`
**Evidence class:** `SOFTWARE_PREPARATION_ONLY`

เอกสารนี้เตรียมงานที่ทำได้ใน repository ก่อน external owner มาถึง โดยไม่อ้างว่า OIDC/mTLS, key custody หรือ Acer hardware ผ่านการทดสอบจริง และไม่เปิดสิทธิ์ external execution, clinical validation หรือ production deployment

> Local preparation cannot set `AUTHORIZED_BY_EXTERNAL_OWNER`, `external_authority=NONE` must remain unchanged, and the pilot gate remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.

## Prepared artifacts

| Area | Artifact | What it proves | What it does not prove |
|---|---|---|---|
| Identity transport | `WAVE_1_IDENTITY_TRANSPORT_CONFIG_TEMPLATE.env.example` | Required variable names, isolated non-production placeholders, safe algorithms, local certificate path boundary and locked flags | Live issuer/JWKS, token claims, mTLS handshake, certificate rotation/revocation or network ACL |
| Wave 1 manifest | `wave1_software_preparation.py` and `evals/micro_rag/evidence/wave1-software-preparation-template-20260820.json` | Exact GV-04/GV-08/GV-06 tracks, test IDs, external inputs, stop conditions and status model | Appointment, signed scope, test-window approval, external evidence or gate pass |
| Machine-readable schema | `evals/micro_rag/evidence/wave1-software-preparation-schema-v1.json` | Top-level shape and locked status/authorization values | Full execution evidence validation or external decision |
| Custody preparation | `tracks.key_custody` in the manifest | Ceremony, dual-control, public-key-only, rotation/revocation and lost-device prerequisites | Manufacturer CA, HSM/secure element, non-exportability or independent custody read-back |
| Acer preparation | `tracks.acer_bench` in the manifest | S-001–S-015 mapping, physical fixture inputs, safety stop conditions and exact non-production boundary | COM-port enumeration, driver/thermal/power-loss/soak or physical serial evidence |

## Track readiness

### GV-04 OIDC/mTLS

The software package lists ID-001 through ID-007 and requires an isolated issuer/JWKS reference, test client/certificate-chain reference, approved ACL, rotation/revocation plan and independent read-back. The environment template contains placeholders only. The existing local validators remain the source of software checks: `validate_oidc_config.py` validates configuration shape and safe algorithms; `validate_mtls_config.py` validates local file presence and private-key permissions. Their live IdP, handshake, certificate lifecycle and segmentation claims remain `UNVERIFIED`.

### GV-08 Device Trust and key custody

The package lists KT-001 through KT-007 and makes the prohibited boundary explicit: no private key material, factory secret, seed map or production credential may enter source, database, log or evidence. Before execution, the custody owner must provide manufacturer CA/HSM/secure-element reference, dual-control ceremony, inventory/public-key reference, rotation/revocation distribution and lost-device/manual-fallback evidence. The existing `KeyCustodyRegistry` remains a software contract/fixture only; hardware-backed custody remains `UNVERIFIED`.

### GV-06 Acer Spin N17H2

The package maps S-001 through S-015 to the existing `SERIAL_BENCH_VALIDATION_PLAN.md`. Physical execution requires the exact phrase `I_HAVE_A_NONPRODUCTION_LOOPBACK`, an approved loopback fixture, synthetic telemetry only, isolated network, operator role and independent witness. The known current blocker remains `pyserial_unavailable` with no enumerated ports. A passing framing harness is software evidence and cannot substitute for physical evidence.

## Fail-closed rules

The manifest rejects unknown top-level fields, raw identity/contact data, secret markers, production targets, track deletion, status changes, execution changes, missing external inputs, missing stop conditions and any mutation of the authorization boundary. All tracks remain `PREPARED_SOFTWARE_ONLY`, `NOT_STARTED` and `UNVERIFIED` for hardware/external validation.

The external owner must appoint roles and approve scope/window/rollback before any track is opened. If scope, identity, certificate, key custody, privacy, integrity, recovery, network or clinical safety mismatches occur, the track stops and remains blocked. New evidence may be submitted only after the relevant blocked gate is explicitly reopened by its external governance process.

## Next gate

After Wave 0 owner appointment and signed scope are available, the external coordinator may submit a populated intake using opaque references. The security owner may then prepare an isolated non-production OIDC/mTLS window, the custody owner may conduct a non-production ceremony and the reliability owner may execute the Acer procedure. None of these actions may use production credentials, raw patient data, production HIS, live ward network or unapproved hardware.
