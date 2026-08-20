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
| P1-004 | Define external forensic anchor adapter | Integration engineer + security auditor | Local forensic chain | Independent append-only/WORM verification and retention transcript | In Progress |
| P1-005 | Approve clinical shadow-mode protocol | Clinical reviewer | `CLINICAL_SAFETY_SHADOW_MODE.md` | Human-factors review, stop conditions, alarm-fatigue review and sign-off record | In Progress |
| P1-006 | Prepare clinical validation readiness package | Clinical reviewer + security auditor | P1-005 shadow-mode review, protocol and safety gates | Intended/excluded use, consent/waiver, owners, fallback, rollback, independent review and preflight evidence | In Progress |
| P1-007 | Coordinate external validation and pilot readiness | Integration owner + clinical governance coordinator | P1-001–P1-006 evidence register | Ten named gates, owner assignments, evidence refs, blocker reasons and no-authorization boundary | In Progress |
| P1-008 | Operate independent review session and controlled pilot gate | Independent reviewer + governance coordinator | GV-10 dossier, P1-007 gate registry, signed evidence export | Review lifecycle, severity-coded findings, finding-to-gate traceability, close/reopen control and no-authorization boundary | Dry-run complete |

## P2 — Capability expansion

| ID | Task | Owner role | Dependencies | Acceptance evidence | Status |
|---|---|---|---|---|---|
| P2-001 | Build thin BMAX roaming client | Roaming-client engineer | P0-001/002/003/005, stable roaming API | Managed Android identity, encrypted cache, reconnect/conflict and usability evidence | Deferred |
| P2-002 | Add Edge IoT adapters | Edge architect + integration engineer | Device Trust and adapter contract | MQTT/WebSocket/Serial/BLE adapter tests and packet translation evidence | In Progress |
| P2-003 | Add clinically reviewed NEWS/MEWS adapter | Clinical reviewer + Edge architect | P1-005 | Versioned scoring contract, explainability, shadow-mode and clinical validation | Proposed |
| P2-004 | Add narrow operational Micro-RAG | Knowledge engineer + security auditor | `MICRO_RAG_EVALUATION_CONTRACT.md`, approved corpus, memory rules | Retrieval evaluation, provenance, redaction and refusal tests; no raw identity corpus | In Progress |
| P2-005 | Evaluate worker mesh | Reliability operator + control-room coordinator | Idempotency, locks, retries and approval model | Failure-injection, duplicate-run and rollback evidence | Proposed |
| P2-006 | Evaluate multimodal analytics | Clinical reviewer + security auditor | Consent, privacy and validation plan | Separate research protocol and risk review; not a pilot default | Deferred |

### P1-005 clinical shadow-mode status note

`clinical_shadow_mode.py`, `test_clinical_shadow_mode.py` and `test_clinical_shadow_mode_negative.py` pass policy completeness, non-diagnostic labels, raw-identity marker rejection, bounded context, review timing, duplicate review rejection, denominator-labelled non-accuracy metrics and stop/resume controls. P1-005 remains pending clinical governance approval, named owners, staff walkthrough, human-factors review, alarm-fatigue review, retention decision and real-world shadow evidence.

### P1-008 independent review operations status note

`independent_review_operations.py` and `test_independent_review_operations.py` provide a software-only review session contract with `OPEN`/`CLOSED` lifecycle, duplicate-protected evidence acceptance, severity-coded findings, finding-to-gate/evidence traceability, post-close mutation lock, raw-identity rejection and an explicit no-authorization boundary. P1-008 dry-run regression passed; appointment of an independent reviewer, signed evidence export, real external-gate evidence and governance decision remain unverified.

### P1-007 external validation coordination status note

`external_validation_package.py`, `test_external_validation_package.py` and `test_external_validation_gate_matrix.py` provide a software coordination contract with 10 external gates: clinical governance, privacy/security, HIS/admission, identity/transport, Fixed Hub host, hardware/recovery, forensic anchor, Device Trust, clinical operations and independent review. Gate evidence is traceable and duplicate-protected; blocked gates require explicit reopen; blockers remain visible; `real_world_authorization` is permanently false. `gv10_evidence.py` and `test_gv10_evidence.py` add SHA-256, timezone-aware timestamp, redaction, provenance and chain-of-custody validation for GV-10. P1-007/GV-10 are coordination artifacts, not clinical authorization.

### P1-006 clinical validation readiness status note

`clinical_validation_readiness.py` and `test_clinical_validation_readiness.py` provide a fail-closed preflight that distinguishes `NOT_READY_FOR_CLINICAL_VALIDATION` from `READY_FOR_EXTERNAL_GOVERNANCE_REVIEW`. The preflight cannot self-assert clinical evidence or authorize real-world testing; all clinical, privacy, consent, device, HIS, transport, fallback and independent-review gates remain external.

### P1-004 external anchor status note

`external_anchor.py` defines an independent-provider adapter boundary with request/receipt identity checks, deterministic idempotency, fail-closed client configuration and explicit `EXTERNAL_PROVIDER_RECEIPT_UNVERIFIED` evidence class. `test_external_anchor_contract.py` and `test_external_anchor_fault_injection.py` pass accepted receipt, replay, deletion refusal, tamper detection and receipt mutation scenarios. The provider is a software stub; external append-only/WORM service, authenticated transport, trusted timestamp, retention and cross-boundary verification remain open.

### P1 Device Trust status note

`key_custody_contract.py` and `test_key_custody_contract.py` provide a software-only provisioning registry contract. Dual-control activation, explicit hardware-attestation flags, rotation linkage, terminal revocation, lost-device transition and private-key material exclusion pass. Hardware-backed custody, manufacturer CA, firmware interoperability, MDM integration and independent revocation distribution remain unverified.

### P1 operational trunk status note

`backup_restore.py` implements a SQLite backup-API snapshot, manifest/checksum, secret-like artifact rejection, isolated-target restore and exact non-production confirmation. `test_backup_restore.py` passes software backup/restore, tamper detection and restore refusal checks. This is a dry-run/software baseline; encrypted destination, retention approval, real Acer filesystem and disaster-recovery evidence remain pending.

`deployment_readiness.py` validates pilot-safe defaults, loopback binding, non-wildcard hosts, OIDC configuration shape, runtime path separation and Device Trust staging. Windows templates under `deploy/windows/` prepare Acer auto-run through an operator-controlled PowerShell/Task Scheduler adaptation. They do not install services, configure Windows Firewall, create accounts or prove Acer boot/service recovery.

### P2-002 status note

The transport-neutral adapter skeleton and architecture are implemented in `edge_iot_adapters.py` and `P2_EDGE_IOT_ADAPTER_ARCHITECTURE.md`. MQTT, WebSocket, Serial and BLE profiles normalize bounded frames into `TelemetryPacket v1`; they reject PII/secret/command fields, unknown fields, identity mismatch, malformed/oversized frames and missing signature envelopes. Device Trust canonical signature compatibility, duplicate/out-of-order sequence rejection and the Serial first-transport software gate pass. The Serial framing/partial-read harness in `serial_framing.py` passes CRC, truncation, resynchronization, overflow and reconnect-reset tests. The offline pressure suite in `network_pressure_simulation.py` passes burst saturation, sustained partial reads, CRC/PII/replay faults and reconnect scenarios while preserving configured bounds. The dry-run-safe `serial_bench_runner.py` passes its safety regression and read-only Acer inventory found Windows 11 Pro build `26200`, Python `3.14.3` and no enumerated serial ports. `SERIAL_BENCH_VALIDATION_PLAN.md` and `NETWORK_PRESSURE_BACKPRESSURE_PLAN.md` define the Acer physical procedures; real broker, BLE/RF, serial-driver, gateway-attestation, Acer hardware and network evidence remain `Unverified`.

### P2-004 status note

The deterministic Micro-RAG hallucination/provenance baseline remains corpus-v2 and includes Thai/English provenance plus bilingual adversarial-injection checks. The approved-document registry and rebuildable-index adapter are now hardened to v2 with deterministic JSON snapshot export/import, manifest/index hash verification, lifecycle transition guards, actor/reason capture, timezone-aware lifecycle timestamps, stale-index detection, failed-rebuild atomicity and chunk-level provenance checks. The model-agnostic response adapter now verifies evidence chunk hashes, eligible corpus state, citation scope, timezone-aware metadata and Thai support tokens.

The live evaluation runner now rebuilds retrieval through `DocumentRegistry` and `RebuildableIndexAdapter` rather than injecting fixture retrieval directly. Synthetic approval epoch is fixed so repeated samples share deterministic registry/index provenance. The pinned `gemini-2.5-flash` revision `001` index-backed rerun returned `0/8` because all eight calls were provider HTTP 429; this is classified as `PROVIDER_LIMITED_REQUIRES_REVIEW`, not a quality score. The current `gemini-3-flash-preview` revision `3-flash-preview-12-2025` index-backed rerun accepted `6/8`, with two provider HTTP 429 failures and zero quality/adapter rejections. Provider-aware repeated-sample aggregation excludes provider failures from the quality denominator and marks each current model path `INSUFFICIENT_SAMPLES` because only one live sample exists. The persistence ownership/retention contract and fail-closed runtime readiness preflight are implemented; current readiness reports are `NOT_READY` with clinical and production authorization false. The repeated-sample protocol, review decision validator and controlled-pilot external-review handoff are implemented; the current handoff is `BLOCKED_INCOMPLETE_EVIDENCE` with pilot gate `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`, 7 blocked gates and 3 open gates. The controlled-pilot operations validator, blocker reopen contract, artifact manifest hash and signed-style non-cryptographic receipt simulation are now implemented; the current operations decision remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`. Runtime semantic index deployment, external persistence approval, repeated samples, human review and clinical retrieval remain pending; the P2-004 gate remains open.

### Wave 0 release freeze and owner-approval status note

`freeze_release_candidate.py` refreshed `evals/micro_rag/evidence/release-candidate-freeze-20260820.json` with `RELEASE_FREEZE_STATUS=PASS` for current source revision `ef2eec369b4fb2fa24b34c03558b37fef7b5f194`; `RELEASE_FREEZE_REFRESH_REPORT_20260820.md` records 318 tracked files, current local/origin alignment, secret-marker/runtime scans and locked claim boundary. `test_release_freeze_candidate.py` verifies current source/origin alignment, selected tracked-file hashes, valid/forbidden claims, 7-blocked/3-open/0-passed gate snapshot and no-authorization fields. The manifest excludes its own hash and is repository/software evidence only; historical reports retain their original freeze revisions. `WAVE_0_OWNER_APPROVAL_GAP_REPORT_20260820.md` records external role appointments, signed scope, test window, rollback, stop authority, custody and independent verification as pending. `WAVE_1_TECHNICAL_VALIDATION_PACKAGE_20260820.md` prepares isolated non-production matrices for GV-04 OIDC/mTLS, GV-08 key custody and GV-06 Acer bench; `WAVE_1_PREFLIGHT_REPORT_20260820.md` records local contract/dry-run PASS but `pyserial_unavailable`, no enumerated ports and physical validation pending. `wave1_external_execution_readiness.py` and `test_wave1_external_execution_readiness.py` now fail closed at `READY_FOR_OWNER_APPOINTMENT`, list 15 missing external prerequisites and are included in `run_all_tests.py`; external execution remains `NOT_STARTED`.

`wave1_software_preparation.py`, `export_wave1_software_preparation.py` and `test_wave1_software_preparation.py` add a strict software-only preparation manifest for GV-04 OIDC/mTLS, GV-08 key custody and GV-06 Acer S-001–S-015. `WAVE_1_SOFTWARE_PREPARATION_PACKAGE_20260820.md` and `WAVE_1_IDENTITY_TRANSPORT_CONFIG_TEMPLATE.env.example` provide the non-production configuration boundary, external-input checklist, stop rules, dual-control/key-custody requirements and exact `I_HAVE_A_NONPRODUCTION_LOOPBACK` physical gate. The manifest is `SOFTWARE_PREPARATION_READY` with execution `NOT_STARTED`; it rejects unknown fields, raw contacts, secret markers, production targets and authorization mutations. This closes a software-preparation gap only; live IdP/mTLS, manufacturer custody, Acer COM/driver/power-loss and external gate evidence remain `Unverified`/`Blocked`.

`wave0_owner_appointment_intake.py`, `export_wave0_owner_appointment_intake.py` and `test_wave0_owner_appointment_intake.py` implement and verify a strict blank-safe owner appointment intake. The package requires nine distinct opaque role references, signed scope/window/stop/rollback/custody references, timezone-aware timestamps, redaction PASS and independent verification while rejecting unknown fields, raw identity/contact data and authorization mutations. `WAVE_0_EXTERNAL_OWNER_APPOINTMENT_PACKAGE_20260820.md` documents the onboarding and stop rules; exported template/schema are machine-readable evidence artifacts. This is a software-verified intake package with state `READY_FOR_OWNER_APPOINTMENT`; it does not appoint external owners, authorize execution or change production status.

### External Authorization API Wave E dossier status note

`EXTERNAL_AUTHORIZATION_API_WAVE_E_EXTERNAL_VALIDATION_DOSSIER.md` prepares a non-production external validation boundary with named-role requirements, ten entry criteria, a 12-test matrix, strict `wave-e-evidence-v1` record schema, dossier coordination state machine, stop/recovery rules and independent read-back requirements. The package is now `READY_FOR_EXTERNAL_OWNER_APPOINTMENT`, which means internal schema/readiness review is complete; external execution remains `NOT_STARTED` because no external endpoint, test IdP, mTLS material, ACL approval, custody service, independent reviewer or clinical authorization is present in the repository. `READY_FOR_INDEPENDENT_REVIEW` is an evidence/dossier state, not an API status, `PASSED`, clinical authorization or production authorization. The dossier cannot change local authorization flags or External Gate status.

`external_authorization_api_wave_e_evidence.py`, `test_wave_e_evidence.py`, `export_wave_e_evidence_schema.py`, `wave_e_evidence_validation_runner.py`, `evals/micro_rag/evidence/wave-e-evidence-schema-v1.json` and `evals/micro_rag/evidence/wave-e-evidence-schema-validation-20260820.json` implement, generate and record record-level and bundle-level evidence: exact T-01–T-12 coverage, shared scope/window/contract binding, timezone-aware ordered timestamps, result/failure fields, artifact/manifest hashes, signature/key/read-back fields, idempotency/reconciliation, stop/recovery separation of duties, topology/limiter semantics, strict unknown-field rejection and locked no-authorization fields. The local validation report is software/schema evidence only and does not change external execution or gate status.

### External Authorization API Wave A–D hardening status note

`external_authorization_api_simulator.py` และ `test_external_authorization_api_simulator.py` now cover the local Wave A–D hardening boundary. Wave A includes private state, append-only audit-store abstraction, deterministic lock serialization and explicit incident fail-stop. Wave B includes expiry/revocation, revision/event-hash/cache-version stale rejection and hashed restart snapshot recovery. Wave C includes bounded retry advice, uncertain-commit reconciliation, chunk manifest integrity, strict type checks and allowlisted audit payloads. Wave D includes Wave 0 governance binding, finding evidence membership, exact contract-version negotiation and simulator-side response-authenticity denial. The resulting evidence class is `SOFTWARE_VERIFIED`, `SIMULATION_ONLY` or `SOFTWARE_VERIFIED/PARTIAL` according to the control; it is not external authorization. EA-020 remains `EXTERNAL_UNVERIFIED`, the API remains in-memory, and the product remains **NOT_PRODUCTION_READY**.

### P2 backlog review and next-phase actions

| ID | Current assessment | Main blocker/risk | Next-phase action |
|---|---|---|---|
| P2-001 | Deferred | Requires closed P0 identity/API/hardware gates and real Android device evidence | Design the thin client only after roaming API, managed identity, encrypted cache and conflict contract are frozen |
| P2-002 | In Progress | Transport-specific trust, framing, replay, disconnect and hardware behavior remain unverified | Freeze transport-neutral contract, complete Serial software gate, then bench-test one actual transport before adding MQTT/BLE/WebSocket |
| P2-003 | Proposed | Clinical scoring requires reviewer ownership, versioned policy and shadow-mode validation | Keep out of pilot default; prepare clinical review package after P1-005 |
| P2-004 | In Progress | Current live samples are insufficient; Gemini 2.5 is 0/8 provider-limited and Gemini 3 is 6/8 with two provider 429; runtime readiness and operations handoff are NOT_READY/BLOCKED | Repeat each pinned model in an appropriate provider window, obtain at least two compatible samples, then complete external persistence owner/retention/access review, runtime semantic-index evaluation and external gate review |
| Pilot operations gate | In Progress | Local manifest/receipt simulation is not external custody or authorization | Obtain independent reviewer, external receipt/trusted timestamp, gate-owner decisions and signed stop/go record |
| External Authorization unblock | In Progress | Seven blocked gates remain externally unverified; 3 open gates still need review closure | Execute Wave 0 owner/reviewer appointment, freeze scope, then follow `EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md` through technical, integration, operations and independent adjudication waves |
| Wave 0 governance | In Progress | Local contract reaches `GOVERNANCE_PACKAGE_READY_FOR_EXTERNAL_REVIEW` only; release freeze is software-verified, but appointments, signatures and custody remain external-unverified | Use `WAVE_0_OWNER_APPROVAL_GAP_REPORT_20260820.md` to obtain named external appointments, signed scope, approved test window, stop authority and external freeze/custody verification before any real test boundary opens |
| External Authorization API handoff | In Progress | Offline simulator validates the local Wave A–D contract only; real endpoint, transport, ACL, signed response, expiry/revocation, custody and reviewer remain unverified | Use the amended Wave E dossier, `wave-e-evidence-v1`/bundle schema and owner-approval report to obtain external owners, approved non-production endpoint and independent evidence without changing local authorization flags |
| External Authorization API v2 hardening | In Progress | Wave A–D software controls now have targeted regression evidence: atomic/private state, append-only audit abstraction, incident fail-stop, concurrency, expiry/revocation/cache version, restart snapshot, bounded retry/chunk validation, strict evidence binding, governance binding and response-authenticity denial; EA-020 remains external-unverified | Preserve the no-authorization boundary, run master regression, then obtain separately approved non-production external API validation with signed response, OIDC/mTLS, ACL, expiry/revocation and independent read-back evidence |
| Production-readiness audit | Blocked | `PRODUCTION_READINESS_EVIDENCE_AUDIT.md` decision is `NOT_PRODUCTION_READY`; 5 Implemented, 1 Experimental, 6 Unverified, 1 Planned | Resolve external IdP/HIS, Acer host/hardware, forensic anchor/key custody, backup destination, clinical governance and 10-gate blockers before any production claim |
| P2-005 | Proposed | Worker mesh can create duplicate jobs, unsafe retries and autonomous clinical side effects | Start with non-clinical backup/report jobs, idempotency/locks/failure injection and explicit approval gates |
| P2-006 | Deferred | Voice/facial/emotion signals require consent, data minimization and clinical validation | Keep outside pilot; create separate research protocol and privacy threat model |

The next implementation phase should prioritize the **External Authorization unblock plan** beginning with Wave 0 governance setup, while P2-001/P2-002 remain gated by P0 hardware and trust evidence. No P2 item may be closed by software tests alone when it changes clinical behavior, identity, secrets, external transmission, network exposure or durable state.

## Task rules

Every task must name an owner, dependencies, explicit acceptance evidence, data boundary, approval requirement and rollback/stop condition. A task that changes clinical behavior, identity, secrets, external transmission, network exposure or durable state cannot be closed by a software unit test alone. Wave 0 governance records and API simulation may prepare external review but cannot self-assign external authority.
