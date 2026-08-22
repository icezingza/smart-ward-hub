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
- **P0-004 — In Progress:** `test_p0_recovery.py` plus `power_loss_recovery_harness.py` verify atomic checkpoint restart, stale temporary-file isolation, corrupt JSON fail-closed behavior, unsupported/malformed checkpoint handling, PII-bearing checkpoint rejection, sequence-inconsistency rejection and SQLite WAL/synchronous-FULL reopen behavior. `checkpoint_invariant_hardening=SOFTWARE_VERIFIED` is recorded in `P0_POWER_LOSS_SOFTWARE_EVIDENCE.json`. Real Acer power cut, disk-full, filesystem corruption and storage-controller recovery remain unverified.
- **P0-005 — Planned:** no Acer Spin N17H2 hardware bench evidence exists in the sandbox. It requires the physical device, approved bench protocol, network topology and operator transcript.

## P1 — Resilience, custody and clinical review

| ID | Task | Owner role | Dependencies | Acceptance evidence | Status |
|---|---|---|---|---|---|
| P1-001 | Define encrypted backup/restore and retention | Reliability operator | Backup skill overlay | Strict manifest schema, size/hash/integrity checks, isolated successful restore transcript, approved encryption/destination/retention/RPO/RTO | In Progress |
| P1-002 | Harden host and least-privilege deployment | Host operator + security auditor | P0 hardware/network observations | Strict 13-control software-preparation contract, target-host OS/firewall/account/patch/disk/service evidence and external readiness decision | In Progress |
| P1-003 | Define Device Trust key custody/provisioning | Security auditor + registry manager | Device Trust baseline | KT-001–KT-007 software-preparation contract, adversarial lifecycle gate, manufacturer CA/HSM/secure-element or approved alternative design, rotation and lost-device drill | In Progress |
| P1-004 | Define external forensic anchor adapter | Integration engineer + security auditor | Local forensic chain | AC-001–AC-007 software-preparation contract, adversarial/failure-injection gate, independent append-only/WORM verification and retention transcript | In Progress |
| P1-005 | Approve clinical shadow-mode protocol | Clinical reviewer | `CLINICAL_SAFETY_SHADOW_MODE.md` | SM-001–SM-007 software-preparation contract, adversarial/clinical-safety negative gate, human-factors review, stop conditions, alarm-fatigue review and sign-off record | In Progress |
| P1-006 | Prepare clinical validation readiness package | Clinical reviewer + security auditor | P1-005 shadow-mode review, protocol and safety gates | CV-001–CV-010 software preflight contract, adversarial/clinical-safety negative gate, intended/excluded use, consent/waiver, owners, fallback, rollback, independent review and external preflight evidence | In Progress |
| P1-007 | Coordinate external validation and pilot readiness | Integration owner + clinical governance coordinator | P1-001–P1-006 evidence register | Ten-gate coordination contract, adversarial/failure-injection gate lifecycle, owner assignments, evidence refs, blocker/reopen reasons and no-authorization boundary | In Progress |
| P1-008 | Operate independent review session and controlled pilot gate | Independent reviewer + governance coordinator | GV-10 dossier, P1-007 gate registry, signed evidence export | Review lifecycle, severity-coded findings, finding-to-gate traceability, close/reopen control and no-authorization boundary | Dry-run complete |

## P2 — Capability expansion

| ID | Task | Owner role | Dependencies | Acceptance evidence | Status |
|---|---|---|---|---|---|
| P2-001 | Build thin BMAX roaming client | Roaming-client engineer | P0-001/002/003/005, stable roaming API | Managed Android identity, encrypted cache, reconnect/conflict and usability evidence | Deferred |
| P2-002 | Add Edge IoT adapters | Edge architect + integration engineer | Device Trust and adapter contract | MQTT/WebSocket/Serial/BLE adapter tests and packet translation evidence | In Progress |
| P2-003 | Add clinically reviewed NEWS/MEWS adapter | Clinical reviewer + Edge architect | P1-005 | Versioned scoring contract, explainability, shadow-mode and clinical validation | Proposed |
| P2-004 | Add narrow operational Micro-RAG | Knowledge engineer + security auditor | `MICRO_RAG_EVALUATION_CONTRACT.md`, approved corpus, memory rules | Retrieval evaluation, provenance, redaction and refusal tests; no raw identity corpus | In Progress |
| P2-005 | Evaluate worker mesh | Reliability operator + control-room coordinator | Idempotency, locks, retries and approval model | Failure-injection, duplicate-run and rollback evidence | In Progress |
| P2-006 | Evaluate multimodal analytics | Clinical reviewer + security auditor | Consent, privacy and validation plan | Separate research protocol and risk review; not a pilot default | Deferred |

### P1-005 clinical shadow-mode status note

`clinical_shadow_mode.py`, `test_clinical_shadow_mode.py` and `test_clinical_shadow_mode_negative.py` pass policy completeness, non-diagnostic labels, raw-identity marker rejection, bounded context, review timing, duplicate review rejection, denominator-labelled non-accuracy metrics and stop/resume controls. The runtime hardening additionally rejects unsafe owner/reference types, raw contact/secret markers, naive timestamps, duplicate activation and invalid stop/resume references. `p1_005_clinical_shadow_readiness.py`, its template/schema, `P1_005_CLINICAL_SHADOW_READINESS_REPORT.md` and `test_p1_005_phase_end_hardening_gate.py` provide SM-001–SM-007 readiness and adversarial evidence. P1-005 remains pending clinical governance approval, named owners, staff walkthrough, human-factors review, alarm-fatigue review, retention decision and real-world shadow evidence.

### P1-008 independent review operations status note

`independent_review_operations.py` and `test_independent_review_operations.py` provide a software-only review session contract with `OPEN`/`CLOSED` lifecycle, duplicate-protected evidence acceptance, strict type/identity/contact/secret/timestamp validation, severity-coded findings, finding-to-gate/evidence traceability, deterministic post-close state-fingerprint mutation detection, raw-identity rejection and an explicit no-authorization boundary including `pilot_gate_status`. `p1_008_independent_review_readiness.py`, its exporter, template/schema, `P1_008_INDEPENDENT_REVIEW_READINESS_REPORT.md`, `test_p1_008_independent_review_hardening.py` and `test_p1_008_phase_end_hardening_gate.py` provide IR-001–IR-007 software readiness and adversarial evidence. Focused regression, adversarial suite, template/schema validation, private-key scan and `git diff --check` pass. Appointment of an independent reviewer, signed evidence export, real external-gate evidence, external findings/decision and governance authorization remain unverified; status remains `NOT_PRODUCTION_READY`, `PENDING_EXTERNAL_REVIEW` and `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.

### Wave 0 external owner appointment intake status note

`wave0_owner_appointment_intake.py` now validates exact top-level/nested field sets, repository identity, complete blank-safe template shape, scope text length/duplicate/raw-identity/secret boundaries, lowercase freeze SHA-256, ordered timezone-aware test windows, strict nine-role separation, independent-verifier separation, stop/rollback/evidence references and the locked authorization boundary. `test_wave0_owner_appointment_intake.py`, `test_wave0_owner_appointment_hardening.py`, `test_wave0_owner_appointment_phase_end_hardening.py` and `WAVE_0_OWNER_APPOINTMENT_READINESS_REPORT_20260821.md` provide software evidence. Submitted intake returns `owner_appointment_ready=true` only as a local validation result while `execution_ready=false` and `external_execution_authorized=false` remain locked. Wave 0 is `READY_FOR_OWNER_APPOINTMENT`; no external role is verified as appointed and external execution remains `NOT_STARTED`.

### P1-007 external validation coordination status note

`external_validation_package.py`, `test_external_validation_package.py` and `test_external_validation_gate_matrix.py` provide a software coordination contract with 10 external gates: clinical governance, privacy/security, HIS/admission, identity/transport, Fixed Hub host, hardware/recovery, forensic anchor, Device Trust, clinical operations and independent review. The hardened runtime rejects unsafe package/gate/domain/owner/evidence references, raw identity/contact/secret markers, malformed/naive timestamps, unsupported claims, duplicate evidence/blockers, invalid registry keys, execution-status mutations and authorization mutations. Blocked gates require explicit reopen; blockers remain visible; `real_world_authorization`, clinical validation and production authorization remain false. `p1_007_external_validation_readiness.py`, its template/schema, `P1_007_EXTERNAL_VALIDATION_READINESS_REPORT.md` and `test_p1_007_phase_end_hardening_gate.py` add 10-gate machine-readable readiness and adversarial evidence. `gv10_evidence.py` and `test_gv10_evidence.py` add SHA-256, timezone-aware timestamp, redaction, provenance and chain-of-custody validation for GV-10. P1-007/GV-10 are coordination artifacts, not clinical authorization.

### P1-006 clinical validation readiness status note

`clinical_validation_readiness.py` and `test_clinical_validation_readiness.py` provide a fail-closed preflight that distinguishes `NOT_READY_FOR_CLINICAL_VALIDATION` from `READY_FOR_EXTERNAL_GOVERNANCE_REVIEW`. The runtime contract now rejects unsafe owner/reference and intended/excluded-use fields, non-boolean gates, self-asserted real-world authorization and external evidence classes, while returning a copied locked authorization boundary. `p1_006_clinical_validation_readiness.py`, its template/schema, `P1_006_CLINICAL_VALIDATION_READINESS_REPORT.md`, `test_p1_006_clinical_validation_hardening.py` and `test_p1_006_phase_end_hardening_gate.py` provide CV-001–CV-010 software-preparation and adversarial evidence. The preflight cannot self-assert clinical evidence or authorize real-world testing; all clinical, privacy, consent, device, HIS, transport, fallback and independent-review gates remain external.

### P1-004 external anchor status note

`external_anchor.py` defines an independent-provider adapter boundary with strict provider identity, request/receipt binding, deterministic idempotency, fail-closed publish/verify outage handling and explicit `EXTERNAL_PROVIDER_RECEIPT_UNVERIFIED` evidence class. `p1_004_external_anchor_readiness.py` and its template/schema define AC-001–AC-007 as software-preparation tracks with all external evidence pending. The phase-end gate adds anchor/timestamp/provider mutations, type confusion, digest boundary, replay, delete refusal, provider-record tamper, false verification and outage cases. The provider is a software stub; external append-only/WORM service, authenticated transport, trusted timestamp, retention and cross-boundary verification remain open.

### P1 Device Trust status note

`key_custody_contract.py` and `test_key_custody_contract.py` provide a software-only provisioning registry contract. `p1_003_key_custody_readiness.py` and its template/schema define KT-001–KT-007 as software-preparation tracks with all external evidence pending. The phase-end hardening gate adds mutation isolation, None/type confusion rejection, duplicate-approver collapse, hardware-attestation fail-closed checks, rotation replay rejection, terminal-state enforcement and private-material block scanning. Hardware-backed custody, manufacturer CA, firmware interoperability, MDM integration and independent revocation distribution remain unverified.

### P1 operational trunk status note

`backup_restore.py` implements a SQLite backup-API snapshot, strict manifest schema, source/backup identity binding, timezone-aware timestamp validation, artifact size/SHA-256/integrity binding, secret-like artifact rejection, isolated-target restore and exact non-production confirmation. `test_backup_restore.py` passes successful software restore plus unknown-field, missing-database, size/path/timestamp mutation, tamper, confirmation and secret-boundary refusal checks. This is a dry-run/software baseline; encrypted destination, retention/RPO/RTO approval, real Acer filesystem and disaster-recovery evidence remain pending.

`deployment_readiness.py` validates pilot-safe defaults, loopback binding, non-wildcard hosts, OIDC configuration shape, runtime path separation and Device Trust staging. `p1_002_host_hardening_readiness.py` adds a strict 13-control software-preparation manifest covering least privilege, runtime separation, disk/firewall boundaries, safe defaults, identity transport, time/patch state, service recovery, backup, privacy and monitoring. The template/schema and `P1_002_HOST_HARDENING_READINESS_REPORT.md` keep host execution `NOT_STARTED`, physical validation `UNVERIFIED` and clinical validation `PENDING`; the regression rejects unknown fields, unsafe state mutations, raw identity/secret markers, incomplete control sets and non-opaque evidence references. Windows templates under `deploy/windows/` prepare Acer auto-run through an operator-controlled PowerShell/Task Scheduler adaptation. They do not install services, configure Windows Firewall, create accounts or prove Acer boot/service recovery.

### P2-002 status note

The transport-neutral adapter skeleton and architecture are implemented in `edge_iot_adapters.py` and `P2_EDGE_IOT_ADAPTER_ARCHITECTURE.md`. MQTT, WebSocket, Serial and BLE profiles normalize bounded frames into `TelemetryPacket v1`; they reject PII/secret/command fields, unknown fields, identity mismatch, malformed/oversized frames and missing signature envelopes. Device Trust canonical signature compatibility, duplicate/out-of-order sequence rejection and the Serial first-transport software gate pass. The Serial framing/partial-read harness in `serial_framing.py` passes CRC, truncation, resynchronization, overflow and reconnect-reset tests. The offline pressure suite in `network_pressure_simulation.py` passes burst saturation, sustained partial reads, CRC/PII/replay faults and reconnect scenarios while preserving configured bounds. The dry-run-safe `serial_bench_runner.py` passes its safety regression and read-only Acer inventory found Windows 11 Pro build `26200`, Python `3.14.3` and no enumerated serial ports. `SERIAL_BENCH_VALIDATION_PLAN.md` and `NETWORK_PRESSURE_BACKPRESSURE_PLAN.md` define the Acer physical procedures; real broker, BLE/RF, serial-driver, gateway-attestation, Acer hardware and network evidence remain `Unverified`.

### P2-004 status note

The deterministic Micro-RAG hallucination/provenance baseline remains corpus-v2 and includes Thai/English provenance plus bilingual adversarial-injection checks. The approved-document registry and rebuildable-index adapter are now hardened to v2 with deterministic JSON snapshot export/import, manifest/index hash verification, lifecycle transition guards, actor/reason capture, timezone-aware lifecycle timestamps, stale-index detection, failed-rebuild atomicity and chunk-level provenance checks. The model-agnostic response adapter now verifies evidence chunk hashes, eligible corpus state, citation scope, timezone-aware metadata and Thai support tokens.

The live evaluation runner now rebuilds retrieval through `DocumentRegistry` and `RebuildableIndexAdapter` rather than injecting fixture retrieval directly. Synthetic approval epoch is fixed so repeated samples share deterministic registry/index provenance. The pinned `gemini-2.5-flash` revision `001` index-backed rerun returned `0/8` because all eight calls were provider HTTP 429; this is classified as `PROVIDER_LIMITED_REQUIRES_REVIEW`, not a quality score. The current `gemini-3-flash-preview` revision `3-flash-preview-12-2025` index-backed rerun accepted `6/8`, with two provider HTTP 429 failures and zero quality/adapter rejections. Provider-aware repeated-sample aggregation excludes provider failures from the quality denominator and marks each current model path `INSUFFICIENT_SAMPLES` because only one live sample exists. The persistence ownership/retention contract and fail-closed runtime readiness preflight are implemented; current readiness reports are `NOT_READY` with clinical and production authorization false. The repeated-sample protocol, review decision validator and controlled-pilot external-review handoff are implemented; the current handoff is `BLOCKED_INCOMPLETE_EVIDENCE` with pilot gate `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`, 7 blocked gates and 3 open gates. The controlled-pilot operations validator, blocker reopen contract, artifact manifest hash and signed-style non-cryptographic receipt simulation are now implemented; the current operations decision remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`. Runtime semantic index deployment, external persistence approval, repeated samples, human review and clinical retrieval remain pending; the P2-004 gate remains open.

### Wave 0 release freeze and owner-approval status note

`freeze_release_candidate.py` refreshes `evals/micro_rag/evidence/release-candidate-freeze-20260820.json`; the machine-readable manifest is authoritative for current source revision, origin alignment, file count, timestamp, secret-marker/runtime scans and locked claim boundary. `RELEASE_FREEZE_REFRESH_REPORT_20260820.md` defines the refresh policy, while `test_release_freeze_candidate.py` verifies current source/origin alignment, selected tracked-file hashes, valid/forbidden claims, 7-blocked/3-open/0-passed gate snapshot and no-authorization fields. The manifest excludes its own hash and is repository/software evidence only; historical reports retain their original freeze revisions. `WAVE_0_OWNER_APPROVAL_GAP_REPORT_20260820.md` records external role appointments, signed scope, test window, rollback, stop authority, custody and independent verification as pending. `WAVE_1_TECHNICAL_VALIDATION_PACKAGE_20260820.md` prepares isolated non-production matrices for GV-04 OIDC/mTLS, GV-08 key custody and GV-06 Acer bench; `WAVE_1_PREFLIGHT_REPORT_20260820.md` records local contract/dry-run PASS but `pyserial_unavailable`, no enumerated ports and physical validation pending. `wave1_external_execution_readiness.py` and `test_wave1_external_execution_readiness.py` now fail closed at `READY_FOR_OWNER_APPOINTMENT`, list 15 missing external prerequisites and are included in `run_all_tests.py`; external execution remains `NOT_STARTED`.

`wave1_software_preparation.py`, `export_wave1_software_preparation.py`, `test_wave1_software_preparation.py`, `test_wave1_software_preparation_hardening.py` and `test_wave1_software_preparation_phase_end_hardening.py` provide a strict software-only preparation manifest for GV-04 OIDC/mTLS, GV-08 key custody and GV-06 Acer S-001–S-015. The validator now enforces exact nested field sets, track-definition/type integrity, caller-mutation isolation, raw identity/contact/secret and production-target rejection, lowercase freeze hash and locked `NOT_STARTED`/`UNVERIFIED` states. `WAVE_1_TECHNICAL_FOUNDATION_READINESS_REPORT_20260821.md`, `WAVE_1_SOFTWARE_PREPARATION_PACKAGE_20260820.md` and `WAVE_1_IDENTITY_TRANSPORT_CONFIG_TEMPLATE.env.example` provide the non-production configuration boundary, external-input checklist, stop rules, dual-control/key-custody requirements and exact `I_HAVE_A_NONPRODUCTION_LOOPBACK` physical gate. The phase-end gate also verifies the external-readiness artifact remains `READY_FOR_OWNER_APPOINTMENT` with 15 missing prerequisites. This closes software-preparation gaps only; live IdP/mTLS, manufacturer custody, Acer COM/driver/power-loss and external gate evidence remain `Unverified`/`Blocked`.

`wave2_integration_forensic_readiness.py`, `export_wave2_integration_forensic_readiness.py`, `test_wave2_integration_forensic_hardening.py` and `test_wave2_integration_forensic_phase_end_hardening.py` add a strict non-production readiness manifest for GV-03 HIS/FHIR and GV-07 forensic-anchor boundaries. Wave 2 now reports `WAVE2_SOFTWARE_PREPARATION_READY`, execution `NOT_STARTED`, external integration `UNVERIFIED` and clinical validation `PENDING`; the runtime forensic verification response reports local anchor readback separately and explicitly keeps `external_anchor_verified=false`. Focused GV-03/GV-07 regressions and adversarial receipt/token/purge/provider/schema mutations pass. Real HIS/FHIR profile and transcript, external WORM receipt, trusted timestamp, retention/custody and cross-boundary verification remain external/unverified; local FileAnchorStore is not WORM or tamper-proof.

`wave3_governance_host_clinical_readiness.py`, `export_wave3_governance_host_clinical_readiness.py`, `test_wave3_governance_host_clinical_hardening.py` and `test_wave3_governance_host_clinical_phase_end_hardening.py` add a strict four-track software-readiness manifest for GV-02 privacy/security, GV-05 Acer host, GV-09 clinical operations and GV-01 clinical governance. The validator enforces exact nested fields, 16 prerequisite bindings, raw identity/contact/secret rejection, host/clinical claim boundaries, caller-mutation isolation and locked `NOT_STARTED`/`UNVERIFIED`/`PENDING` states. P1-002/P1-005/P1-006 regression and Wave 3 phase-end gate pass; privacy review, Acer host evidence, staff competency/manual fallback, clinical protocol/committee/consent and external authorization remain unverified/pending.

`wave4_independent_review_package.py`, `export_wave4_independent_review_package.py`, `test_wave4_independent_review_package_hardening.py` and `test_wave4_independent_review_package_phase_end_hardening.py` add a consolidated GV-10/Wave E coordination index. The package maps exactly T-01..T-12, hashes 22 local repository artifacts, binds each artifact to source revision/freeze manifest, enforces relative-path and role/evidence-class rules, rejects raw identity/secret/authorization mutations and keeps `wave_e_bundle_state=NOT_EXECUTED`, `independent_review_status=NOT_STARTED` and `external_owner_appointment=PENDING_EXTERNAL_APPOINTMENT`. This package is local software coordination only; release-freeze is a top-level binding excluded from its own artifact list to avoid circular self-hashing; no external test record or signed decision is created.

`independent_reviewer_readiness_preflight.py`, `export_independent_reviewer_readiness_preflight.py`, `test_independent_reviewer_readiness_preflight_hardening.py` and `test_independent_reviewer_readiness_preflight_phase_end_hardening.py` add the next reviewer-precheck layer. The preflight rechecks the locked authorization boundary, exact T-01..T-12 mapping, 22-artifact index binding and 12 IRP-01..IRP-12 reviewer checklist items; it keeps `submission_status=NOT_SUBMITTED`, `reviewer_appointment=PENDING_EXTERNAL_APPOINTMENT`, `external_decision=NOT_ISSUED`, `wave_e_bundle_state=NOT_EXECUTED` and records 12 pending external inputs. Reviewer-preflight and phase-end tests pass; this is not an external submission or decision.

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
| P2-005 | In Progress | In-process contract now covers non-clinical job allowlist, idempotency, role separation, bounded retries, leases, stale reconciliation and audit integrity; durable/distributed execution remains unverified | Preserve software-only boundary, then separately design approved durable queue/crash-recovery and operator deployment evidence before any external or clinical worker action |
| P2-006 | Deferred | Voice/facial/emotion signals require consent, data minimization and clinical validation | Keep outside pilot; create separate research protocol and privacy threat model |

### P2-002 Serial evidence status note

`serial_bench_evidence_contract.py` and `serial_bench_runner.py` now bind dry-run/physical-loopback records to `serial-bench-evidence-v1`, exact S-001..S-015 coverage, redaction flags, forbidden-marker scan, physical confirmation, hardware claim state and canonical SHA-256 payload integrity. `test_serial_bench_evidence_contract.py` and `test_p2_002_serial_evidence_phase_end_hardening.py` pass runner regression, PII/coverage/hash tamper rejection, physical PASS binding, no-shell check, private-key scan and diff hygiene. This is software evidence only: Acer COM enumeration, driver/loopback, disconnect/reconnect, Device Trust physical handoff, queue-pressure bench, power-loss and production network remain unverified; P2-002 stays In Progress.

### P2-005 worker control-plane status note

`worker_control_plane.py` and `test_worker_control_plane.py` provide an in-process, deterministic, non-clinical worker control contract. The implementation allowlists `BACKUP_REPORT` and `EVIDENCE_REPORT`, enforces requester/approver separation, idempotency fingerprints, duplicate job-id refusal, bounded attempts, expiring leases, stale-lease blocking, explicit recovery reconciliation, fail-closed handler outcomes, caller-mutation isolation and an append-only hash-chained audit stream. `durable_worker_store.py` now adds a `software_fixture`-only SQLite WAL/FULL durable store with transactional submit/claim, restart persistence, bounded retry, committed expired-lease blocking, explicit reconciliation and audit-chain verification; production durable mode fails closed. `test_p2_005_worker_phase_end_hardening.py` and `test_p2_005_durable_worker_phase_end_hardening.py` add focused/adversarial execution, static rejection of scheduler/network/subprocess side effects, SQLite integrity checks, private-key scan and diff hygiene. `worker_queue_backup.py` now binds the durable worker SQLite fixture to the P1-001 SQLite backup API with a schema/source-revision/database-hash binding, separate-target restore, exact non-production confirmation and no-authorization flags; `test_worker_queue_backup.py` and `test_p2_005_worker_backup_phase_end_hardening.py` pass binding/tamper/restore checks. This is software-preparation evidence only: encryption-at-rest, backup destination/custody, retention/RPO/RTO, distributed locks, external delivery, OS supervision, clinical state mutation and production authorization remain unverified.

### Wave E execution preflight status note

`wave_e_execution_preflight.py` and `export_wave_e_execution_preflight.py` now produce a local `READY_FOR_EXTERNAL_OWNER_APPOINTMENT` handoff snapshot with exact E-01..E-10 coverage, distinct authority roles, source-revision binding, no-authorization snapshot, package hash and `execution_permitted=false`. `test_wave_e_execution_preflight.py` and `test_wave_e_execution_preflight_phase_end_hardening.py` pass missing-criteria, role-collision, authorization-mutation, unsafe-reference, no-network and secret-scan checks. All E-01..E-10 remain unasserted because external owners, signed scope/window, endpoint, IdP/mTLS, ACL, custody, trusted clock, stop authority and reviewer evidence are not present. This is coordination/preflight software evidence only and cannot move Wave E to execution or any gate to `PASSED`.

### External decision record status note

`external_decision_record.py` and `export_external_decision_record.py` now define a blank-safe sign-off record contract for `decision_id`, `submission_id`, manifest/scope/window binding, decision basis, expiry, rollback/stop/revocation refs, signature/certificate/trust-chain refs and independent read-back. The validator accepts only a template or `EXTERNAL_DECISION_RECORD_RECEIVED` with a non-authorizing decision (`BLOCKED`, `REQUIRES_CLARIFICATION` or `ACCEPTED_WITH_RESIDUAL_RISK`), while forcing `external_decision_verified=false`, `authorization_promoted=false`, `external_execution_authorized=false`, `production_authorized=false`, `clinical_validation_authorized=false` and the locked boundary. Focused/adversarial and phase-end tests cover status escalation, authenticity promotion, missing/duplicate/tampered refs, expiry, raw identity/contact, secret markers, numeric-only contact refs, no-side-effect and private-key scans. This prepares sign-off intake only; it cannot create external authority, verify a real signature/custody record or authorize pilot/clinical/production.

### Wave 1 external evidence intake status note

`wave1_external_evidence_intake.py` and `export_wave1_external_evidence_intake.py` now define a strict intake contract for all 15 Wave 1 prerequisites across GV-04, GV-08 and GV-06. The template is blank-safe with `MISSING_EXTERNAL` for every prerequisite, `READY_FOR_OWNER_APPOINTMENT`, `NOT_SUBMITTED`, `NOT_STARTED` and the locked `NONE`/`false` authorization boundary. Submitted intake may carry typed opaque owner/evidence/read-back refs, lowercase SHA-256, timezone-aware timestamps and redaction `PASS`, but it remains `READY_FOR_OWNER_APPOINTMENT` and cannot self-assert `READY_FOR_EXTERNAL_EXECUTION` or `PASSED`. The focused/adversarial suite and phase-end gate cover exact 15-item coverage, duplicate/tamper/raw-identity/secret/timestamp/hash/status mutation, no-network behavior and private-key scanning. All 15 external prerequisites remain missing and require external owners, physical fixtures or independent evidence.

### Cross-package evidence reconciliation status note

`evidence_reconciliation.py` now cross-checks the top-level release freeze, Wave 4 local index, independent reviewer preflight, Wave E execution preflight snapshot and Wave 0 owner-appointment template. It verifies freeze-bound artifact hashes, package states, T-01..T-12/mapping counts, E-01..E-10 missing state, redaction/no-PII flags and the locked `NONE`/`false` authorization boundary. `test_evidence_reconciliation.py` and `test_evidence_reconciliation_phase_end_hardening.py` pass hash-tamper, authorization-mutation, Wave E escalation, immutable frozen-source and no-side-effect checks. Current result is `RECONCILED_WITH_EXTERNAL_BLOCKERS`; source revisions that differ from the top-level freeze are classified as `ANCESTOR_OR_STALE_UNVERIFIED` and require ancestry verification or regeneration before external submission. This guard cannot change any gate to `PASSED`.

The next implementation phase should prioritize the **External Authorization unblock plan** beginning with Wave 0 governance setup, while P2-001/P2-002 remain gated by P0 hardware and trust evidence. No P2 item may be closed by software tests alone when it changes clinical behavior, identity, secrets, external transmission, network exposure or durable state.

## Task rules

Every task must name an owner, dependencies, explicit acceptance evidence, data boundary, approval requirement and rollback/stop condition. A task that changes clinical behavior, identity, secrets, external transmission, network exposure or durable state cannot be closed by a software unit test alone. Wave 0 governance records and API simulation may prepare external review but cannot self-assign external authority.

### External Decision Lifecycle Evaluator status note

`external_decision_lifecycle.py` implements a deterministic, local-only lifecycle evaluator for external decision records. It covers timezone-aware initialization, expiry, external revocation/supersession, fail-closed simulation blocking, role-bound reopening, resubmission without mutating the prior decision, stale/future polling rejection, revision/event-hash checks, defensive snapshots and a hash-chained `LifecycleEvent` audit stream with `external-decision-lifecycle-v1`. `test_external_decision_lifecycle.py` covers focused/adversarial expiry, revocation, resubmission, reopen, remote-update, stale-poll, authority-separation, snapshot-isolation and invalid-input paths. `test_external_decision_lifecycle_phase_end_hardening.py` adds focused rerun, AST no-network/provider/scheduler scan, no-self-authorization state lock, runtime boundary/schema assertions, private-key scan and `git diff --check`. `export_external_decision_lifecycle.py` produces a blank-safe template snapshot with deterministic record-template hash and state registry. This is software simulation/functional verification only; it does not verify a real external signature, appoint an authority or independent reviewer, execute Wave E, perform clinical validation, or authorize pilot/production. Authorization remains `NONE`/`false`; product status remains `NOT_PRODUCTION_READY`, pilot status remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`, and clinical validation remains pending external governance.

### Internal foundation hardening status note

`internal_foundation_readiness.py` now provides a read-only software preflight for pilot environment, no auto-create/seed, docs disabled, loopback/allowed-host boundaries, OIDC configuration shape, runtime-path separation, bounded numeric settings, runtime-artifact hygiene, private-key marker scanning and the locked no-authorization boundary. `test_internal_foundation_readiness.py` covers valid pilot configuration, invalid bounds, wildcard exposure, source-tree paths, static-token advisory behavior, runtime residue, private-key rejection and boundary preservation. `test_internal_foundation_phase_end_hardening.py` adds focused rerun, AST no-network/provider/scheduler scan, runtime readiness assertions, claim lock, private-key scan and diff hygiene; both are included in `run_all_tests.py`. This strengthens the internal software foundation only. Global/device/payload telemetry limits, memory-pressure reporting, canonical device identifiers and configuration bounds are now implemented; cross-component recovery matrix, operational status snapshot and target-host evidence remain next internal work. Acer host, real IdP/mTLS, HIS, external custody, clinical governance and independent authorization remain external/unverified.

### Cross-component recovery expansion status note

The recovery matrix has been expanded to 11 local software fault-injection scenarios covering SQLite/WAL, telemetry checkpoint, backup/restore, local forensic anchor, durable worker restart/stale lease, worker audit corruption, worker-queue schema binding mismatch, WAL writer contention and checkpoint persistence failure. The matrix preserves normal resume only after verified roundtrip and enforces `resume_permitted_after_unresolved_fault=false` with `RECONCILIATION_REQUIRED` whenever a component is unverified. Durable worker health now reports malformed audit JSON as `audit_chain_valid=false` without crashing, and EdgeTelemetryStore rolls back in-memory state when checkpoint persistence fails. This remains local software evidence; physical power-loss, target-host disk/full filesystem, external custody, clinical validation and authorization remain pending.

### Software rollback rehearsal and operational thresholds status note

Implemented isolated software rollback rehearsal across SQLite/WAL database, telemetry checkpoint, audit export, local anchor export and durable worker queue. The rehearsal simulates post-backup drift, restores to separate non-production targets, verifies hashes/integrity/sequence/audit/readback and permits resume only inside the verified software rehearsal target; production and external resume remain false. Added bounded operational thresholds for preflight, database verification, checkpoint/backup/audit/anchor freshness, disk headroom, sync backlog, worker backlog and unresolved alerts. Missing, stale, invalid or over-limit evidence emits remediation codes and blocks resume. Physical host recovery, encrypted destination, clinical validation and external authorization remain pending.

### Operational Remediation & Recovery Decision Rehearsal status note

Implemented a read-only operational remediation rehearsal for stale backup, sync backlog and unresolved alert evidence. The flow is `RECONCILIATION_REQUIRED` -> remediation evidence recheck -> `OPERATOR_CONFIRMATION_REQUIRED` -> `SOFTWARE_RESUME_ELIGIBLE`; actual runtime resume is not executed and production/external resume remain false. Added opaque operator/correlation reference validation, known remediation-code mapping, redacted hash-chained transcript, authorization-boundary violation handling and deterministic evidence exporter. This is local software simulation only; real ward alert handling, clinical escalation, HIS sync and external authorization remain pending.


### Alert/Sync Reconciliation Matrix status note — 22 สิงหาคม 2026

`alert_sync_reconciliation_matrix.py` เพิ่ม pure/read-only decision contract สำหรับ alert acknowledgement, unresolved-alert reset/discharge blocking, incident freeze ที่ขาด forensic package, bounded sync retry, dead-letter classification, sync stale revision และ roaming command stale revision. ทุกผลลัพธ์มี `resume_permitted`, `recovery_decision`, `remediation_code`, reason, opaque references และ locked authorization boundary. Acknowledged alert อนุญาตเฉพาะ software monitoring-resume eligibility; unresolved alert ยังคง block destructive reset/discharge.

`test_alert_sync_reconciliation_matrix.py` ครอบคลุม 12 focused/adversarial cases รวม normal acknowledgement, unresolved alert, missing forensic package, structured sync acknowledgment, retry exhaustion/dead-letter, stale sync revision, stale roaming command, idempotent replay, raw-identity rejection, invalid alert state และ authorization mutation. `test_alert_sync_reconciliation_matrix_phase_end_hardening.py` เพิ่ม AST side-effect scan, no-network/provider/scheduler check, redaction/private-key scan, no-self-authorization assertions, transcript integrity และ `git diff --check`. `export_alert_sync_reconciliation.py` สร้าง read-only redacted machine-readable evidence พร้อม hash-chained transcript.

Focused suite และ phase-end hardening gate ผ่าน. Master regression integration เพิ่มแล้ว แต่ยังต้องรัน master suite, hygiene cleanup, commit/push และ refresh release-freeze ก่อนปิด workstream. หลักฐานทั้งหมดเป็น software simulation/functional verification เท่านั้น; real HIS/EMR sync, clinical escalation, ward alert handling, durable production dead-letter queue, BMAX roaming execution, external forensic anchor และ external authorization ยังคง unverified/pending. Product remains `NOT_PRODUCTION_READY`; pilot remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.


### Fixture-only Sync/Alert Replay Harness status note — 22 สิงหาคม 2026

`sync_alert_replay_harness.py` เพิ่ม immutable fixture-only state evaluator สำหรับ retryable sync, retry exhaustion/dead-letter, dead-letter replay confirmation, duplicate acknowledgment, acknowledgment bundle mismatch, partial sync write และ stale/future/current roaming snapshot revision. Decision แยก `replay_permitted`/`resume_permitted` ออกจาก `replay_executed`, `purge_executed` และ `mutation_performed` ซึ่งต้องเป็น `false` เสมอใน harness.

`test_sync_alert_replay_harness.py` ครอบคลุม 12 focused/adversarial cases. `test_sync_alert_replay_harness_phase_end_hardening.py` ตรวจ no network/provider/scheduler side effect, fixture-only read-only contract, redaction/private-key scan, no-self-authorization boundary, hash-chained transcript และ `git diff --check`. `export_sync_alert_replay.py` สร้าง redacted machine-readable evidence พร้อม source revision และ transcript integrity.

Focused และ phase-end gates ผ่านแล้ว; master regression integration เพิ่มแล้ว. ยังต้องรัน master regression, hygiene cleanup, commit/push และ refresh release-freeze ก่อนปิด workstream. หลักฐานเป็น software simulation/functional verification เท่านั้น; HIS/EMR จริง, SQLite/WAL transaction recovery บน target host, durable external dead-letter execution, clinical escalation, BMAX execution และ external authorization ยังคง unverified/pending.


### Durable Worker Replay Contract status note — 22 สิงหาคม 2026

`durable_worker_replay_contract.py` เชื่อม `DurableWorkerStore` กับ lease expiry, restart reconciliation, retry-limit/dead-letter classification และ `worker_queue_backup` isolated restore บน SQLite `software_fixture` target. Lease ที่หมดอายุถูก block เป็น `LEASE_EXPIRED_REQUIRES_RECONCILIATION` ก่อน requeue; retry limit ที่หมดถูกจัดเป็น `RETRY_LIMIT_EXCEEDED_DEAD_LETTER`; dead-letter replay ต้องมี explicit operator confirmation และคืนได้สูงสุดเพียง `SOFTWARE_REPLAY_ELIGIBLE` โดย `replay_executed=false`.

`test_durable_worker_replay_contract.py` ครอบคลุม 4 focused/adversarial scenarios และตรวจ WAL, synchronous=FULL, integrity, audit chain, queue backup binding, restored state, redaction และ no-authorization boundary. `test_durable_worker_replay_contract_phase_end_hardening.py` ตรวจ no network/provider/scheduler side effect, no-self-authorization, private-key/redaction scan และ `git diff --check`. Master regression integration เพิ่มแล้ว; ยังต้องรัน master suite, hygiene cleanup, commit/push และ refresh release-freeze ก่อนปิด workstream.

หลักฐานเป็น SQLite fixture/software simulation เท่านั้น; distributed worker, scheduler, encrypted backup custody, external dead-letter broker, Windows service recovery, clinical mutation และ external authorization ยังคง unverified/pending. Product remains `NOT_PRODUCTION_READY`; pilot remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.


### Operator Worker Recovery Transcript status note — 22 สิงหาคม 2026

`worker_recovery_transcript.py` เพิ่ม redacted, hash-chained operator-facing transcript สำหรับ lease expiry, lease reconciliation, dead-letter observation, dead-letter replay eligibility และ queue-backup binding. Raw job/worker/reconciliation/backup references ถูกแทนด้วย opaque digests; transcript บังคับ role allowlist, timezone-aware event time, bounded details, marker scan และ sequence/hash verification.

`test_worker_recovery_transcript.py` ครอบคลุม 4 focused/adversarial cases รวม lifecycle completeness, tamper detection, raw reference rejection, unsafe role rejection และ secret marker rejection. `export_worker_recovery_transcript.py` สร้าง machine-readable evidence พร้อม source revision, redaction flag และ locked authorization boundary. `test_worker_recovery_transcript_phase_end_hardening.py` เพิ่ม AST no-network/provider/scheduler scan, no-self-authorization, private-key/redaction scan, exporter round-trip และ `git diff --check`. Master regression integration เพิ่มแล้ว; ยังต้องรัน master suite, hygiene cleanup, commit/push และ refresh release-freeze ก่อนปิด workstream.

หลักฐานนี้เป็น local software simulation และไม่ยืนยัน human operator sign-off, production worker behavior, distributed queue, encrypted backup custody, clinical action หรือ independent review. Product remains `NOT_PRODUCTION_READY`; pilot remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.


### Operator Approval / Read-back Contract status note — 22 สิงหาคม 2026

`worker_recovery_approval.py` เพิ่ม exact read-back schema สำหรับ worker recovery transcript โดยบังคับ requester/approver/readback role separation, explicit `I_UNDERSTAND_SOFTWARE_REHEARSAL_RESUME` confirmation, timezone-aware ordered timestamps, transcript SHA-256 binding, queue-backup reference/hash binding, `SOFTWARE_REHEARSAL_ONLY` scope และ `replay_execution_requested=false`/`replay_executed=false`. Boundary mutation, actor collision, transcript/queue tamper, wrong confirmation, timestamp order, unknown field และ raw marker fail closed.

`test_worker_recovery_approval.py` ครอบคลุม 7 focused/adversarial cases. `export_worker_recovery_approval.py` สร้าง redacted machine-readable evidence พร้อม validation, source revision และ locked authorization claim. `test_worker_recovery_approval_phase_end_hardening.py` ตรวจ no network/provider/scheduler side effect, exporter round-trip, no-self-authorization, private-key/redaction scan และ `git diff --check`. Master regression integration เพิ่มแล้ว; ยังต้องรัน master suite, hygiene cleanup, commit/push และ refresh release-freeze ก่อนปิด workstream.

นี่เป็น local software simulation/read-back artifact เท่านั้น ไม่ใช่ human sign-off จริง, external signature, independent reviewer decision, production approval, clinical action หรือ external authorization. Product remains `NOT_PRODUCTION_READY`; pilot remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.


### Cross-Package Evidence Binding Check status note — 22 สิงหาคม 2026

`cross_package_evidence_binding.py` เพิ่ม read-only checker สำหรับผูก worker recovery transcript, operator approval/read-back, durable worker replay evidence และ release-freeze manifest. ตรวจ freeze-listed artifact bytes/hash, transcript integrity, approval transcript/queue refs and hashes, durable software-only boundary, source revisions และ locked authorization. Mismatch จะคืน `RECONCILIATION_REQUIRED` พร้อม remediation code; ไม่เขียนไฟล์/ฐานข้อมูล ไม่ส่งข้อมูล และไม่ promote authorization.

`export_durable_worker_replay.py` เพิ่ม source_revision ให้ durable evidence package สำหรับ cross-package lineage. `test_cross_package_evidence_binding.py` ครอบคลุม synthetic bound fixture, transcript hash mismatch, queue ref mismatch, durable boundary mutation, freeze hash mismatch และ repository binding; `test_cross_package_evidence_binding_phase_end_hardening.py` จะเป็น phase-end gate สำหรับ no side effect, redaction/private-key, no-self-authorization และ exporter round-trip. Workstream อยู่ระหว่าง reconcile/regenerate evidence ให้ artifact hashes และ source revisions สอดคล้อง ก่อน commit/push, refresh freeze และ master regression.

ขอบเขตยังเป็น internal software evidence binding เท่านั้น; `BOUND` ไม่ใช่ production-ready, clinical validation หรือ external authorization. Product remains `NOT_PRODUCTION_READY`; pilot remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.


### Consolidated Internal Handoff Index status note — 22 สิงหาคม 2026

`consolidated_internal_handoff_index.py` เพิ่ม read-only internal navigation index ที่อ้างอิง worker recovery transcript, operator approval/read-back, durable worker replay, cross-package binding snapshot และ release-freeze manifest. ตรวจ binding decision/codes, all binding checks, freeze PASS, source/origin equality, tracked artifact hashes, locked external-gate snapshot (7 blocked/3 open/0 passed), claim boundary และ authorization boundary.

`test_consolidated_internal_handoff_index.py` ผ่าน 7 focused/adversarial cases ครอบคลุม bound index, binding-not-bound, gate snapshot mutation, claim mutation, freeze hash mismatch, authorization mutation และ external-submission lock. `export_consolidated_internal_handoff_index.py` สร้าง redacted machine-readable snapshot. `test_consolidated_internal_handoff_index_phase_end_hardening.py` ตรวจ no network/provider/scheduler side effect, round-trip, redaction/private-key, no-self-authorization และ diff hygiene. Workstream รอ master regression, commit/push และ freeze refresh.

Index นี้เป็น internal handoff navigation artifact เท่านั้น ไม่ใช่ external submission, independent reviewer decision, authorization record หรือ production release approval. Product remains `NOT_PRODUCTION_READY`; pilot remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.


### Evidence Drift Detection / Freeze Integrity Monitor status note — 22 สิงหาคม 2026

`freeze_integrity_monitor.py` เพิ่ม read-only monitor สำหรับตรวจ freeze manifest, source/origin/parent lineage, tracked-file set, SHA-256 ของ freeze-listed files, runtime artifacts, secret hits, locked authorization, external-gate snapshot, cross-package binding และ consolidated handoff index. เคารพ `manifest_self_hash_excluded=true` ของ freeze generator จึงไม่แจ้ง manifest ตัวเองเป็น unfrozen asset.

ผลลัพธ์มี `DRIFT_FREE` หรือ `DRIFT_DETECTED`; drift จะคืน remediation codes เช่น `FREEZE_TRACKED_FILE_HASH_MISMATCH`, `UNFROZEN_TRACKED_FILE`, `HEAD_NOT_ALIGNED_TO_FREEZE`, `RUNTIME_ARTIFACT_PRESENT`, `FREEZE_BOUNDARY_MUTATED`, `EXTERNAL_GATE_SNAPSHOT_MUTATED`, `CROSS_PACKAGE_BINDING_DRIFTED` และ `HANDOFF_INDEX_DRIFTED`. Monitor ไม่แก้ไฟล์ ไม่เขียน runtime state ไม่ส่งข้อมูล และไม่ promote authorization.

`test_freeze_integrity_monitor.py` ผ่าน 7 focused/adversarial cases. `test_freeze_integrity_monitor_phase_end_hardening.py` ตรวจ no network/provider/scheduler side effect, drift-free baseline, manifest self-exclusion, handoff dependency, redaction/private-key และ no-self-authorization. Master integration เพิ่มแล้ว; ยังต้อง commit/push, refresh freeze, master regression และ final hygiene.

ขอบเขตเป็น local software drift scan เท่านั้น ไม่ใช่ continuous production monitoring, remote attestation, clinical validation หรือ external authorization. Product remains `NOT_PRODUCTION_READY`; pilot remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.


### Pre-Handoff Readiness Check status note — 22 สิงหาคม 2026

`pre_handoff_readiness.py` เพิ่ม read-only gate ก่อน internal handoff โดยรวม `freeze_integrity_monitor.py` และ `consolidated_internal_handoff_index.py`. Decision ที่อนุญาตคือ `INTERNAL_HANDOFF_READY` เฉพาะเมื่อ drift เป็น `DRIFT_FREE`, handoff index เป็น `BOUND`, claim/authorization/gate boundaries ตรง locked values, external submission/transmission ปิด และ runtime mutation absent. กรณี mismatch คืน `INTERNAL_HANDOFF_BLOCKED` พร้อม remediation codes.

`test_pre_handoff_readiness.py` ผ่าน 8 focused/adversarial cases ครอบคลุม ready path, drift stop, unbound index, authorization/claim/gate mutation, external submission enablement และ runtime/transmission mutation. `export_pre_handoff_readiness.py` สร้าง redacted internal evidence. Phase-end gate ผ่านหลังแก้ static assertion ให้ตรวจ immutable boundary จาก runtime output ตาม implementation จริง. Master integration ยังต้องเพิ่ม/commit/push, refresh freeze, master regression และ final hygiene.

Pre-handoff check เป็น internal repository handoff readiness เท่านั้น ไม่ใช่ external submission, independent reviewer acceptance, clinical authorization, production approval หรือ runtime resume. Product remains `NOT_PRODUCTION_READY`; pilot remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.


### Pre-Handoff Evidence Manifest Validator status note — 22 สิงหาคม 2026

`pre_handoff_manifest_validator.py` เพิ่ม read-only validator สำหรับ snapshot `pre-handoff-readiness-local.json`. ตรวจ snapshot presence, freeze listing, snapshot SHA-256, source/origin revisions, fresh readiness decision/checks, claim boundary, authorization boundary, external-gate snapshot, external submission, runtime mutation, external transmission และ read-only contract.

`test_pre_handoff_manifest_validator.py` ผ่าน 8 focused/adversarial cases ครอบคลุม valid fixture, missing/path/hash/source mismatch, decision/check mismatch, claim/authorization mutation, external/runtime/transmission mutation และ fresh readiness blocked. `test_pre_handoff_manifest_validator_phase_end_hardening.py` ผ่าน side-effect scan, redacted exporter round-trip, no-self-authorization/private-key scan และ diff hygiene. ยังต้อง commit/push, สร้าง snapshot, refresh freeze, รัน validator หลัง snapshot, master regression และ final hygiene.

Validator เป็น internal manifest consistency check เท่านั้น ไม่ใช่ external submission, independent reviewer acceptance, clinical authorization หรือ production approval. Product remains `NOT_PRODUCTION_READY`; pilot remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.


### Pre-Handoff Manifest ancestor-binding correction — 22 สิงหาคม 2026

พบจาก snapshot rehearsal ว่า snapshot ที่ export ก่อน commit ถูกต้องตาม lifecycle แต่หลัง freeze refresh แล้ว `source_revision` ของ snapshot จะเป็น ancestor ของ freeze source ไม่ใช่ค่าเท่ากัน. Validator เดิมจึงคืน `SNAPSHOT_SOURCE_REVISION_MISMATCH` และ `SNAPSHOT_ORIGIN_REVISION_MISMATCH` อย่างถูกต้องแบบ fail-closed. ปรับ contract ให้ตรวจ `git merge-base --is-ancestor` แบบ read-only และเพิ่ม focused test ยืนยัน ancestor path; exact mismatch ที่ไม่ใช่ ancestor ยังคงถูกบล็อก.


### Pre-Handoff Evidence Selection Policy status note — 22 สิงหาคม 2026

`pre_handoff_evidence_selection.py` เพิ่ม read-only selected-set evaluator สำหรับชุดหลักฐาน internal handoff 9 รายการตาม dependency order: governance handoff → external-review handoff → worker recovery transcript → operator approval/read-back → durable worker replay → cross-package binding → consolidated internal handoff → pre-handoff readiness → pre-handoff manifest validation.

Policy ตรวจ freeze PASS, locked authorization/gate snapshot, required artifact presence, freeze membership, SHA-256, required package decisions, exact dependency order และ runtime artifact exclusion. `export_pre_handoff_evidence_selection.py` สร้าง redacted selected-set snapshot. Focused/adversarial suite 8 cases และ phase-end hardening gate ผ่านครบ. ยังต้อง commit/push, generate selection snapshot, refresh freeze, master regression และ final hygiene.

Selection policy เป็น internal artifact navigation/selection เท่านั้น ไม่ใช่ external submission, reviewer acceptance, authorization record หรือ production approval. Product remains `NOT_PRODUCTION_READY`; pilot remains `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`.


### Pre-Handoff Selection-to-Manifest Consistency status note — 22 สิงหาคม 2026

เพิ่ม `pre_handoff_selection_manifest_consistency.py` สำหรับตรวจ chain ระหว่าง selected-set snapshot, pre-handoff readiness, pre-handoff manifest validation และ freeze manifest. ตรวจ decision, dependency order, selected package/path set, current/freeze SHA-256, freeze lineage แบบ ancestor, manifest-to-readiness binding, package status, claim/authorization/gate locks และ external/runtime locks.

เพิ่ม `export_pre_handoff_selection_manifest_consistency.py`, focused/adversarial suite 8 cases และ phase-end hardening gate. ขั้นตอนที่เหลือคือผูกเข้า master regression, commit/push, สร้าง consolidated consistency snapshot, refresh freeze, รัน master regression และ final hygiene.

ผลนี้เป็น internal software evidence consistency เท่านั้น ไม่ใช่ external submission, independent reviewer acceptance, clinical authorization หรือ production approval.


### Pre-Handoff Reconciliation Gate status note — 22 สิงหาคม 2026

เพิ่ม `pre_handoff_reconciliation_gate.py` สำหรับรวม child gates 4 ชั้น: freeze drift (`DRIFT_FREE`), manifest (`MANIFEST_VALID`), evidence selection (`SELECTED_SET_VALID`) และ selection-to-manifest consistency (`SELECTION_MANIFEST_CONSISTENT`). Aggregate decision เป็น `INTERNAL_HANDOFF_RECONCILIATION_READY` ได้เมื่อ child decisions/remediation codes/checks ผ่านทั้งหมดและ output locks ยังคงปิด.

Focused/adversarial suite 8 cases ผ่าน. Phase-end gate พบว่าใน workspace ก่อน commit aggregate จะ fail closed ด้วย `DRIFT_GATE_FAILED` เพราะ source drift จากไฟล์ใหม่ ซึ่งเป็น expected stop rule; หลัง commit และ refresh freeze ต้องรัน gate ซ้ำจน ready. เพิ่ม redacted aggregate exporter และต้องผูก tests เข้า master regression, commit/push, snapshot/freeze refresh และ final hygiene.


### Evidence Reconciliation Lineage Verification — continuation — 22 สิงหาคม 2026

เพิ่ม `freeze_integrity_monitor.revision_is_ancestor(...)` เป็น local Git ancestry helper แบบ read-only และปรับ `evidence_reconciliation.py` ให้แยก `MATCH`, `ANCESTOR_REQUIRES_REGENERATION` และ `NON_ANCESTOR_BLOCKED` ใน `source_revision_lineage`. `export_evidence_reconciliation.py` ใช้ frozen archive สำหรับ package bytes พร้อมส่ง repository root เป็น lineage context จึงไม่สูญเสีย ancestry evidence.

Focused suite และ phase-end hardening gate ผ่าน: isolated ancestor/non-ancestor/invalid-path checks, existing hash/state/authorization fail-closed checks, frozen-archive exporter, AST no endpoint/network/provider side effect, private-key scan และ `git diff --check`. Current packages Wave 4/reviewer/Wave E เป็น `ANCESTOR_REQUIRES_REGENERATION`; Wave 0 template เป็น `NON_ANCESTOR_BLOCKED` เพราะยังใช้ placeholder source revision. Aggregate reconciliation ยังคง `RECONCILED_WITH_EXTERNAL_BLOCKERS` และ gate decision ยังคง `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`; ancestry verification ไม่ลบ external blocker และไม่อนุญาต submission.


### Evidence Reconciliation Lineage Verification — final closure note — 22 สิงหาคม 2026

หลัง regenerate `evidence-reconciliation-local-20260821.json` และ refresh freeze แล้ว focused/adversarial suite, phase-end hardening gate และ master regression ผ่าน. Final checks ยืนยัน `DRIFT_FREE`, `MANIFEST_VALID`, `SELECTED_SET_VALID`, `SELECTION_MANIFEST_CONSISTENT`, `INTERNAL_HANDOFF_RECONCILIATION_READY`, `freeze_status=PASS`, `HEAD==origin/main`, `HEAD^==freeze.source_revision==freeze.origin_main_revision`, `git diff --check` ผ่าน และ clean working tree.

Lineage result ยังคงแยกเป็น Wave 4/reviewer/Wave E `ANCESTOR_REQUIRES_REGENERATION` และ Wave 0 template `NON_ANCESTOR_BLOCKED`; aggregate evidence status ยังคง `RECONCILED_WITH_EXTERNAL_BLOCKERS` และ `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`. งานนี้ปิดเฉพาะ software-only lineage verification ไม่ปิด external gate, clinical validation หรือ production authorization.


### Internal Handoff Chain Integrity Gate — 22 สิงหาคม 2026

เพิ่ม `internal_handoff_chain_integrity.py` เพื่อผูก `consolidated-internal-handoff-index-local.json`, `pre-handoff-reconciliation-gate-local.json` และ release-freeze manifest เป็น chain เดียวแบบ read-only/fail-closed. Gate ตรวจ freeze PASS, artifact membership/hash, handoff `BOUND`, reconciliation `INTERNAL_HANDOFF_RECONCILIATION_READY`, child decisions/checks, locked claim/authorization/external-gate boundary และ local source-revision lineage. Failure modes คืน `INTERNAL_HANDOFF_CHAIN_BLOCKED` พร้อม remediation codes; ไม่มี external submission, runtime mutation หรือ authorization promotion.

เพิ่ม `export_internal_handoff_chain_integrity.py`, focused/adversarial suite 11 cases และ phase-end hardening gate. ผลผ่านครบ: hash/membership tamper, child drift, authorization/execution lock mutation, invalid/non-ancestor revision, caller-mutation isolation, exporter round-trip, redaction/private-key scan, no network/provider/scheduler/subprocess imports และ `git diff --check`. Evidence snapshot อยู่ที่ `evals/micro_rag/evidence/internal-handoff-chain-integrity-local.json`; master regression และ final freeze cycle ยังต้องทำก่อนปิด workstream.


### Internal Handoff Chain Integrity Gate — final closure — 22 สิงหาคม 2026

หลัง publish snapshot และ refresh freeze แล้ว focused/adversarial suite 11 cases, phase-end hardening gate และ master regression ผ่าน. Final controls ยืนยัน `DRIFT_FREE`, `MANIFEST_VALID`, `SELECTED_SET_VALID`, `SELECTION_MANIFEST_CONSISTENT`, aggregate `INTERNAL_HANDOFF_RECONCILIATION_READY` และ `INTERNAL_HANDOFF_CHAIN_BOUND`; freeze `PASS`, coverage `567 files`, `HEAD==origin/main`, `HEAD^==freeze.source_revision==freeze.origin_main_revision`, clean working tree และ `git diff --check` ผ่าน.

Chain bound เป็น internal software evidence เท่านั้น. External Gates ยังคง `7 BLOCKED / 3 OPEN / 0 PASSED`; external authority, clinical validation, production authorization และ runtime authority ยังคง locked/false/`NONE`.


### Internal Handoff Chain selected-set boundary correction — 22 สิงหาคม 2026

ตรวจพบจากการออกแบบว่าไม่ควรเพิ่ม `internal_handoff_chain_integrity` เข้า `SELECTED_SET`: meta-gate ตรวจ selected handoff artifacts และ pre-handoff reconciliation อยู่แล้ว หากรวม snapshot ของตัวเองเข้า selected set จะเกิด recursive self-hash/dependency cycle. จึงแก้กลับให้ selector คง 9 รายการและให้ chain-integrity อยู่เป็น control ชั้นบนที่ตรวจ artifact hash ผ่าน release-freeze โดยตรง.

Focused selected-set, consistency, aggregate reconciliation และ chain suites ผ่าน รวม 8/8/10/11 cases ตามลำดับ. Phase-end gates ของทั้งสี่ชั้นผ่านหลัง correction และ freeze refresh; chain evidence ยังคง `INTERNAL_HANDOFF_CHAIN_BOUND` โดยไม่เปลี่ยน external authorization boundary.


### Internal Handoff Chain Integrity — non-recursive boundary finalization — 22 สิงหาคม 2026

จากการตรวจ dependency graph เพิ่มเติม ยืนยันว่า `internal_handoff_chain_integrity` ต้องอยู่นอก `SELECTED_SET` และ dependency order เพราะเป็น meta-control ที่ตรวจ selected handoff artifacts และ pre-handoff reconciliation อยู่แล้ว. การรวม snapshot ของตัวเองจะสร้าง recursive self-hash/dependency cycle. Selector จึงคง 9 artifacts ตาม contract เดิม ขณะที่ chain gate ตรวจ artifact ของตัวเองผ่าน freeze membership/hash โดยตรง.

Correction ผ่าน focused selected-set/consistency/aggregate/chain suites และ phase-end gates ครบ. Master regression ผ่านหลัง correction; final freeze `PASS`, selected set กลับเป็น 9 รายการ และ chain decision ยังคง `INTERNAL_HANDOFF_CHAIN_BOUND`. ขอบเขตยังเป็น software-only internal evidence ไม่ใช่ external authorization หรือ production approval.


### Repository Visibility Governance — 22 สิงหาคม 2026

ตรวจ remote ด้วย `gh repo view icezingza/smart-ward-hub --json nameWithOwner,isPrivate,defaultBranchRef` แล้วพบ `nameWithOwner=icezingza/smart-ward-hub`, default branch `main` แต่ `private=false`. เพิ่ม `repository_visibility_governance.py`, redacted exporter, observation artifact, focused/adversarial suite 10 cases, phase-end gate และผูกเข้า `run_all_tests.py`.

Gate คืน `REPOSITORY_VISIBILITY_BLOCKED` พร้อม `REPOSITORY_NOT_PRIVATE` แบบ fail-closed; identity/branch/source/authorization/execution checks ผ่าน แต่ public visibility เป็น blocker. ไม่เปลี่ยน GitHub setting เอง เพราะต้องมี explicit authorization สำหรับ external visibility operation. ต้องเปลี่ยนเป็น private โดยผู้มีอำนาจและ rerun remote observation ก่อนจึงจะปิด blocker ได้. งานนี้เป็น repository governance evidence ไม่ใช่ production/clinical/external authorization.


### Public-Exposure Quarantine Audit — 22 สิงหาคม 2026

เพิ่ม `public_exposure_quarantine.py`, redacted exporter, evidence snapshot, focused/adversarial suite 12 cases และ phase-end hardening gate. Audit ตรวจ freeze manifest, frozen hashes, secret markers, raw HN/AN-like identifiers, synthetic fixture classification, repository visibility และ locked execution boundary.

ผลล่าสุด `PUBLIC_EXPOSURE_QUARANTINED` พร้อม `PUBLIC_REPOSITORY_EXPOSURE_QUARANTINED` เพราะ repository remote เป็น public (`private=false`). Secret scan และ raw identifier scan นอก approved synthetic paths ผ่าน; synthetic test/simulation/presentation identifiers 26 findings ถูกจัดประเภทแยก ไม่ถือเป็น real patient data. Master regression ผ่าน. ต้องรอ explicit authorization เพื่อเปลี่ยน repository visibility เป็น private แล้ว regenerate observation/evidence/freeze และ rerun all gates.


### Exposure-aware Internal Handoff Chain — 22 สิงหาคม 2026

ขยาย `internal_handoff_chain_integrity.py` ให้รับ `public_exposure_quarantine` เป็น independent child control. Chain จะคืน `INTERNAL_HANDOFF_CHAIN_BOUND` ได้ต่อเมื่อ exposure decision เป็น `PUBLIC_EXPOSURE_CLEAR`, remediation ว่าง, checks ผ่านครบ, snapshot ถูก hash-bind ใน freeze และ locked boundary ครบ. เมื่อ repository ยัง public ผลจึงถูก propagate เป็น `INTERNAL_HANDOFF_CHAIN_BLOCKED` พร้อม `EXPOSURE_QUARANTINED` โดยไม่เปลี่ยน authorization หรือ external settings.

Focused chain suite ผ่าน 13 cases; chain phase-end และ public-exposure phase-end gates ผ่าน. Exporter เพิ่ม exposure decision/remediation fields แบบ redacted. การออกแบบยัง non-recursive: chain snapshot ไม่ถูกเพิ่มเข้า selected set.
