# Smart Ward Hub — AI-Native Task Backlog

**Document role:** Traceable work queue for humans and agents  
**Rule:** A task is not complete until its acceptance evidence exists and its status is labelled correctly

## Status vocabulary

`Proposed` → `In Progress` → `Dry-run complete` → `Approved` → `Applied` → `Verified` or `Unverified` → `Closed`/`Rolled back`

## P0 — Pilot deployment gates

| ID | Task | Owner role | Dependencies | Acceptance evidence | Status |
|---|---|---|---|---|---|
| P0-001 | Finalize HIS/Admission Gateway contract | Integration engineer | `HIS_FHIR_INTEGRATION_CONTRACT.md`, outside-in contract | Sandbox contract test with tokenization, TTL, revocation, acknowledgement and idempotency | In Progress |
| P0-002 | Validate real OIDC/JWKS configuration | Security auditor + integration engineer | IdP metadata and test tenant | Issuer/audience/algorithm/rotation/revocation transcript with secrets redacted | In Progress |
| P0-003 | Validate real mTLS transport | Security auditor + host operator | Test CA/cert chain | Handshake, renewal, expiry and failure transcript | In Progress |
| P0-004 | Run power-loss and storage recovery drill | Reliability operator | Acer bench access, backup procedure | Controlled power cut, WAL recovery, checkpoint, disk-full and corruption handling evidence | In Progress |
| P0-005 | Run Acer Spin N17H2 hardware bench validation | Reliability operator | `TABLET_HARDWARE_DECISION.md`, `HUB_REFERENCE_DESIGN.md` | Reboot, thermal, charger/battery, network and service-recovery transcript | Planned |

### P0 status notes

- **P0-001 — In Progress:** local HIS/FHIR sync now requires a structured acknowledgment containing bundle identity, acknowledgment ID, receiving system, server time, accepted FHIR version and accepted profile. Bare `200 OK` and mismatched bundle acknowledgments are rejected before purge. `test_p0_his_admission_contract.py` additionally verifies sandbox opaque tokenization, TTL, revocation, outside-admission idempotency, failure retention and exact-scope purge. Hospital-side token issuer, FHIR profiles, terminology, patient-reference policy, acknowledgment/error contract, CA and support decisions remain open.
- **P0-002 — In Progress:** an offline validator now checks OIDC mode, issuer, audience, HTTPS JWKS URL and safe algorithms while failing closed on missing configuration. Real issuer reachability, JWKS rotation, role mapping, token acceptance and revocation are unverified until a real IdP/test tenant is supplied.
- **P0-003 — In Progress:** an offline validator now checks mTLS file presence and rejects group/other-readable private keys without reading key material. Real certificate chain, client-certificate handshake, renewal, revocation and hospital network segmentation remain unverified.
- **P0-004 — In Progress:** `test_p0_recovery.py` plus `power_loss_recovery_harness.py` verify atomic checkpoint restart, stale temporary-file isolation, corrupt JSON fail-closed behavior, unsupported/malformed checkpoint handling and SQLite WAL/synchronous-FULL reopen behavior. Real Acer power cut, disk-full, filesystem corruption and storage-controller recovery remain unverified.
- **P0-005 — Planned:** no Acer Spin N17H2 hardware bench evidence exists in the sandbox. It requires the physical device, approved bench protocol, network topology and operator transcript.

## P1 — Resilience, custody and clinical review

| ID | Task | Owner role | Dependencies | Acceptance evidence | Status |
|---|---|---|---|---|---|
| P1-001 | Define encrypted backup/restore and retention | Reliability operator | Backup skill overlay | Manifest, checksum and isolated successful restore transcript | Dry-run complete |
| P1-002 | Harden host and least-privilege deployment | Host operator + security auditor | P0 hardware/network observations | OS, firewall, account, patch, disk and service-binding checklist | In Progress |
| P1-003 | Define Device Trust key custody/provisioning | Security auditor + registry manager | Device Trust baseline | Manufacturer CA/HSM/secure-element or approved alternative design, rotation and lost-device drill | In Progress |
| P1-004 | Define external forensic anchor adapter | Integration engineer + security auditor | Local forensic chain | Independent append-only/WORM verification and retention transcript | Planned |
| P1-005 | Approve clinical shadow-mode protocol | Clinical reviewer | `CLINICAL_SAFETY_SHADOW_MODE.md` | Human-factors review, stop conditions, alarm-fatigue review and sign-off record | Pending |

## P2 — Capability expansion

| ID | Task | Owner role | Dependencies | Acceptance evidence | Status |
|---|---|---|---|---|---|
| P2-001 | Build thin BMAX roaming client | Roaming-client engineer | P0-001/002/003/005, stable roaming API | Managed Android identity, encrypted cache, reconnect/conflict and usability evidence | Deferred |
| P2-002 | Add Edge IoT adapters | Edge architect + integration engineer | Device Trust and adapter contract | MQTT/WebSocket/Serial/BLE adapter tests and packet translation evidence | In Progress |
| P2-003 | Add clinically reviewed NEWS/MEWS adapter | Clinical reviewer + Edge architect | P1-005 | Versioned scoring contract, explainability, shadow-mode and clinical validation | Proposed |
| P2-004 | Add narrow operational Micro-RAG | Knowledge engineer + security auditor | `MICRO_RAG_EVALUATION_CONTRACT.md`, approved corpus, memory rules | Retrieval evaluation, provenance, redaction and refusal tests; no raw identity corpus | In Progress |
| P2-005 | Evaluate worker mesh | Reliability operator + control-room coordinator | Idempotency, locks, retries and approval model | Failure-injection, duplicate-run and rollback evidence | Proposed |
| P2-006 | Evaluate multimodal analytics | Clinical reviewer + security auditor | Consent, privacy and validation plan | Separate research protocol and risk review; not a pilot default | Deferred |

### P1 Device Trust status note

`key_custody_contract.py` and `test_key_custody_contract.py` provide a software-only provisioning registry contract. Dual-control activation, explicit hardware-attestation flags, rotation linkage, terminal revocation, lost-device transition and private-key material exclusion pass. Hardware-backed custody, manufacturer CA, firmware interoperability, MDM integration and independent revocation distribution remain unverified.

### P1 operational trunk status note

`backup_restore.py` implements a SQLite backup-API snapshot, manifest/checksum, secret-like artifact rejection, isolated-target restore and exact non-production confirmation. `test_backup_restore.py` passes software backup/restore, tamper detection and restore refusal checks. This is a dry-run/software baseline; encrypted destination, retention approval, real Acer filesystem and disaster-recovery evidence remain pending.

`deployment_readiness.py` validates pilot-safe defaults, loopback binding, non-wildcard hosts, OIDC configuration shape, runtime path separation and Device Trust staging. Windows templates under `deploy/windows/` prepare Acer auto-run through an operator-controlled PowerShell/Task Scheduler adaptation. They do not install services, configure Windows Firewall, create accounts or prove Acer boot/service recovery.

### P2-002 status note

The transport-neutral adapter skeleton and architecture are implemented in `edge_iot_adapters.py` and `P2_EDGE_IOT_ADAPTER_ARCHITECTURE.md`. MQTT, WebSocket, Serial and BLE profiles normalize bounded frames into `TelemetryPacket v1`; they reject PII/secret/command fields, unknown fields, identity mismatch, malformed/oversized frames and missing signature envelopes. Device Trust canonical signature compatibility, duplicate/out-of-order sequence rejection and the Serial first-transport software gate pass. The Serial framing/partial-read harness in `serial_framing.py` passes CRC, truncation, resynchronization, overflow and reconnect-reset tests. The offline pressure suite in `network_pressure_simulation.py` passes burst saturation, sustained partial reads, CRC/PII/replay faults and reconnect scenarios while preserving configured bounds. The dry-run-safe `serial_bench_runner.py` passes its safety regression and read-only Acer inventory found Windows 11 Pro build `26200`, Python `3.14.3` and no enumerated serial ports. `SERIAL_BENCH_VALIDATION_PLAN.md` and `NETWORK_PRESSURE_BACKPRESSURE_PLAN.md` define the Acer physical procedures; real broker, BLE/RF, serial-driver, gateway-attestation, Acer hardware and network evidence remain `Unverified`.

### P2-004 status note

The deterministic Micro-RAG hallucination/provenance baseline is now corpus-v2 and includes Thai/English provenance plus bilingual adversarial-injection checks. The model-agnostic response adapter and approved-document registry/rebuildable-index software baseline are implemented and registered in the master regression suite. A catalog-verified Gemini `gemini-2.5-flash` revision `001` baseline was previously captured at 5/5 and replayed through the corrected adapter at 5/5. A fresh current-prompt Gemini 2.5 run completed at 2/8 with six later provider calls returning HTTP 429, which is recorded as provider-limited partial evidence rather than a model-quality score. A separate live-catalog-verified `gemini-3-flash-preview` revision `3-flash-preview-12-2025` run passed all 8/8 current corpus-v2 cases through the adapter with redaction passing and runtime authority `NONE`. Runtime semantic index deployment, human review and clinical retrieval remain pending; the pinned Gemini 2.5 current-prompt gate remains open for a clean provider-window rerun.

### P2 backlog review and next-phase actions

| ID | Current assessment | Main blocker/risk | Next-phase action |
|---|---|---|---|
| P2-001 | Deferred | Requires closed P0 identity/API/hardware gates and real Android device evidence | Design the thin client only after roaming API, managed identity, encrypted cache and conflict contract are frozen |
| P2-002 | In Progress | Transport-specific trust, framing, replay, disconnect and hardware behavior remain unverified | Freeze transport-neutral contract, complete Serial software gate, then bench-test one actual transport before adding MQTT/BLE/WebSocket |
| P2-003 | Proposed | Clinical scoring requires reviewer ownership, versioned policy and shadow-mode validation | Keep out of pilot default; prepare clinical review package after P1-005 |
| P2-004 | In Progress | Gemini 3 Flash current v2 run passed 8/8, but pinned Gemini 2.5 rerun is provider-limited at 2/8 with six HTTP 429 responses; runtime and human review remain open | Repeat pinned Gemini 2.5 run after rate-limit window, add repeated samples, then implement approved registry persistence and measured semantic index |
| P2-005 | Proposed | Worker mesh can create duplicate jobs, unsafe retries and autonomous clinical side effects | Start with non-clinical backup/report jobs, idempotency/locks/failure injection and explicit approval gates |
| P2-006 | Deferred | Voice/facial/emotion signals require consent, data minimization and clinical validation | Keep outside pilot; create separate research protocol and privacy threat model |

The next implementation phase should prioritize **P2-004 registry/index hardening and model rerun**, while P2-001/P2-002 remain gated by P0 hardware and trust evidence. No P2 item may be closed by software tests alone when it changes clinical behavior, identity, secrets, external transmission, network exposure or durable state.

## Task rules

Every task must name an owner, dependencies, explicit acceptance evidence, data boundary, approval requirement and rollback/stop condition. A task that changes clinical behavior, identity, secrets, external transmission, network exposure or durable state cannot be closed by a software unit test alone.
