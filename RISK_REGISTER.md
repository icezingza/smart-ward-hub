# Smart Ward Hub — Risk Register

สถานะของเอกสารนี้สะท้อน **P0-hardened software baseline** ของ controlled production prototype เท่านั้น ผลทดสอบซอฟต์แวร์ไม่ใช่ clinical validation และไม่ใช่ production-ready certification.

| ID | Risk | Severity | สถานะ | Control/evidence | Residual risk และ next gate |
|---|---|---:|---|---|---|
| R-001 | PII ปรากฏใน Edge logs, cache, checkpoint หรือ export | Critical | Implemented baseline | `patient_token`-only schema, PII key guard, audit redaction, security tests | ต้องทำ host-level และ downstream scan รวมถึง backup/export review |
| R-002 | Static bearer token ถูกขโมยหรือใช้ผิดวัตถุประสงค์ | High | Experimental baseline | fail-closed scopes และ protected configuration | ต้องใช้ OIDC จริง, rotation, revocation, key custody และ mTLS |
| R-003 | Packet replay หรือ out-of-order arrival | High | Implemented software control | per-device monotonic sequence, HTTP 409, replay regression test | ต้องกำหนด device identity, counter reset และ clock policy กับ hardware จริง |
| R-004 | Buffer overflow ทำให้ข้อมูลสูญหาย | High | Implemented/measured | bounded ring buffer, dropped-sample counter, checkpoint recovery | ต้องกำหนด threshold/alert และทดสอบ load profile ของ pilot จริง |
| R-005 | Checkpoint corruption หรือ stale recovery | High | Implemented software baseline | atomic checkpoint, stale-temp isolation, malformed-payload fail-closed and restart tests | ต้องทดสอบ encrypted storage, corruption injection และ restore drill บน host จริง |
| R-006 | SQLite lock หรือ power loss ระหว่างเขียน | High | Experimental software baseline | WAL, synchronous durability, atomic checkpoint, software fault-injection harness and concurrent harness | ต้องทำ hardware power-failure, disk-full และ filesystem recovery tests |
| R-007 | Alert threshold ทำให้ false positive หรือ miss event | Critical | Unverified clinical performance | shadow mode, review categories, stop conditions และ simulation | ต้องมี clinical protocol, sensitivity/specificity, alarm-fatigue review และ clinical sign-off |
| R-008 | FHIR response ทำให้ purge เร็วเกินไป | Critical | Implemented contract baseline | explicit acknowledgment gate, failure retention, FHIR regression | ต้องทดสอบ HIS จริง, timeout/retry, reconciliation และ operator recovery |
| R-009 | Local hash chain ถูกนำเสนอว่า tamper-proof | High | Controlled by wording; external adapter contract in progress | SHA-256 chain, verification endpoint, local append-only adapter, external receipt adapter contract and explicit terminology | ต้องมี external independent WORM anchor, trusted timestamp, key custody และ cross-boundary verification drill; ห้ามใช้คำว่า tamper-proof |
| R-010 | Concurrent workers มี process-local state ไม่สอดคล้องกัน | High | Known limitation | single Edge owner model, thread-safe telemetry store, handover lock | ต้องตัดสินใจ deployment topology หรือเพิ่ม coordinated/shared state ก่อน scale-out |
| R-011 | Unauthorized Host/CORS exposure | Medium | Implemented baseline | TrustedHost, restrictive defaults, optional CORS, regression test | ต้องทำ firewall, reverse-proxy และ network segmentation review |
| R-012 | Clinical operator ตีความ signal เป็น diagnosis | Critical | Process control required; P1-005/P1-006 software gates added | shadow-mode labeling, safe-label validator, stop/resume contract, preflight requires excluded uses and training gate | ต้องมี training, signed clinical SOP, clinical governance approval, human-factors review and audit evidence |
| R-013 | Backup ไม่สามารถ restore เมื่อจำเป็น | High | Planned | backup/restore runbook foundation | ต้องตั้ง schedule, retention, encrypted backup และ restore drill จริง |
| R-014 | Schema change ทำให้ device fleet ใช้งานไม่ได้ | High | Controlled by versioning | TelemetryPacket v1 lock and change control | ต้องมี schema registry และ migration policy สำหรับ v2 |
| R-015 | Request flood หรือ burst ทำให้ Edge service ถูกใช้ทรัพยากรเกิน | High | Implemented process-local control | sliding-window limiter, `429`, `Retry-After`, rate-limit regression | ต้อง calibrate per-device/endpoint quotas และใช้ gateway/coordinated limiter ใน multi-process deployment |
| R-016 | Audit event ถูกแก้ไข สูญหาย หรือมี PII | High | Implemented local baseline | structured JSONL, request ID, fsync, recursive redaction, zero-PII regression | ต้องส่งเข้า centralized append-only/WORM audit pipeline, access control, retention และ monitoring |
| R-017 | Handover sync ซ้ำทำให้ purge ซ้ำหรือทำลาย evidence | Critical | Implemented single-process control | persisted `HandoverRecord.synced`, `SyncAttempt`, `RLock`, idempotent replay test | ต้องทดสอบ multi-process/crash boundary และกำหนด retention ที่ไม่ทำให้ destructive gate หมดอายุ |
| R-018 | Local forensic anchor ทำให้เกิด false assurance ว่ามี external immutability | High | Local hardening + external adapter contract; provider unverified | local adapter now validates inputs, uses record hash/idempotency/readback; external receipt identity and mutation-fault tests pass | ต้องเชื่อม external service ที่บริหารแยกกัน, authenticated transport, trusted timestamp, retention และ verify chain ข้าม trust boundary |
| R-038 | Review session ถูกปิดโดยไม่มี evidence traceability หรือ finding ที่ตรวจซ้ำได้ | High | P1-008 software baseline | `IndependentReviewSession` บังคับ accepted evidence, gate/evidence linkage, severity และ post-close mutation lock | ต้องแต่งตั้ง reviewer อิสระ, ใช้ signed export, รัน reproduce tests และบันทึก finding closure/reopen ในระบบ governance จริง |
| R-039 | การรับ evidence เข้าตรวจถูกตีความเป็น clinical หรือ production authorization | Critical | P1-008 no-authorization boundary | `clinical_validation_authorized`, `production_authorized` และ `real_world_authorization` ถูกตรึงเป็น false; authorization methods reject | ต้องมี clinical owner/committee decision, external gate evidence และ controlled pilot approval แยกจาก software |
| R-040 | Provider rate limiting ทำให้ model score ถูกตีความเป็น quality failure หรือ pass | High | P2-004 runner classification control | รายงานแยก `PROVIDER_LIMIT_OR_TRANSIENT`, `RUNTIME_OR_ADAPTER_ERROR` และ `quality_or_contract_rejection`; ทุก result เก็บ bounded error type | ต้องรันซ้ำใน provider window ที่เหมาะสม, ทำ repeated samples และห้ามรวม provider failures ใน quality denominator |
| R-041 | Registry/index snapshot ถูกใช้เป็น production source of truth โดยไม่มี owner/retention/access control | High | P2-004 software snapshot baseline | v2 snapshot มี schema/hash verification, atomic export/import และ stale/index integrity guard | ต้องกำหนด persistence owner, encryption/retention/access policy, backup/restore และ runtime semantic-index governance ก่อน deployment |
| R-042 | จำนวน repeated model samples ไม่พอ แต่ผล sample เดียวถูกสื่อสารเป็น reliability score | High | P2-004 repeated-sample aggregator | aggregator บังคับ `min_samples>=2`, ตรวจ compatible model/corpus/index provenance และ status `INSUFFICIENT_SAMPLES` | ต้องทำ repeated samples ใน provider window ที่เหมาะสมและกำหนด sample-size/review protocol ก่อนสรุป quality |
| R-043 | Readiness preflight ถูกตีความเป็น runtime/clinical approval | Critical | P2-004 readiness preflight | preflight เปิดสถานะสูงสุดเพียง `READY_FOR_EXTERNAL_GOVERNANCE_REVIEW`; `clinical_validation_authorized`, `production_authorized`, `runtime_authority` ถูกตรึง false/NONE | ต้องมี external persistence/access evidence, runtime backend verification, clinical governance และ controlled pilot authorization แยกต่างหาก |
| R-044 | Repeated-sample decision ถูกใช้เป็น reliability/clinical score ทั้งที่ protocol ยังไม่ผ่าน minimum samples | High | P2-004 repeated-sample protocol and decision validator | บังคับ `min_samples>=2`, fixed provenance, provider/quality denominator separation และ `BLOCKED_INCOMPLETE_EVIDENCE` | ต้องได้รับ compatible samples เพิ่มและให้ reviewer อนุมัติ analysis plan ก่อนสรุปผล |
| R-045 | External-review coordination package ถูกตีความเป็น controlled-pilot authorization | Critical | P2-004 controlled pilot handoff | handoff ใช้ `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`, 7 blocked/3 open gates และตรึง authorization false | ต้องมี independent review, clinical governance, external gate evidence และ authorization decision แยกจาก software package |
| R-046 | Local SHA-256 manifest หรือ signed-style receipt ถูกตีความเป็น external WORM, trusted timestamp หรือ cryptographic signature | High | Controlled-pilot operations manifest simulation | manifest ตรวจ artifact hash, chain field และ receipt simulation ที่ระบุ `external_authority=NONE` | ต้องมี external receipt, trusted timestamp, independent custody และ real key custody evidence ข้าม trust boundary |
| R-047 | Blocker analysis และ 5-wave plan ถูกใช้แทน external owner appointment, signed scope หรือ authorization decision | Critical | `analyze_controlled_pilot_blockers.py`, `EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md` | analysis ตรวจ 7 blockers และจัดลำดับ owner/evidence/stop condition แต่คง authorization false | ต้องมี named external owners, explicit approval, test-window record, signed scope, expiry, rollback และ independent decision |
| R-048 | Local Wave 0 governance record ถูก self-attest ว่าเป็น appointment/signature/custody จริง | Critical | `WAVE_0_GOVERNANCE_CONTRACT.md`, `wave0_governance.py` | validator บังคับ `PENDING_EXTERNAL_VERIFICATION`, `external_authority=NONE` และเปิดสูงสุดเพียง review-ready | ต้องมี external directory/appointment evidence, signed scope, independent custody และ reviewer verification นอก baseline |
| R-049 | Test window หมดอายุหรือ scope เปลี่ยน แต่ยังใช้ manifest/freeze เดิม | High | `wave0_governance.py`, `WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md` | ตรวจ timezone-aware expiry, freeze version และ append-only policy | ต้องสร้าง window/manifest version ใหม่พร้อม previous hash, reason และ external notification |
| R-050 | Offline External Authorization API simulator ถูกตีความว่าเป็นหลักฐานของ API transport, reviewer identity หรือ external decision จริง | Critical | `external_authorization_api_simulator.py`, `EXTERNAL_AUTHORIZATION_API_SIMULATION_CONTRACT.md` | simulator บังคับ `simulation=true`, audit chain, idempotency และ authorization flags false | ต้องมี real API endpoint, OIDC/mTLS, ACL, signed response, clock, custody, outage/retry และ independent read-back evidence |
| R-051 | Status polling เห็น `REQUIRES_CLARIFICATION` แล้วถูกใช้เป็น approval หรือไม่ติดตาม expiry/revocation | High | API simulator report และ expanded reviewer checklist | status machine จำกัด transition และคง `BLOCKED_PENDING_EXTERNAL_AUTHORIZATION` | ต้องมี external decision lifecycle, expiry, revocation propagation, escalation, reviewer sign-off และ stop authority |
| R-052 | API command ล้มเหลวหลัง commit แต่ก่อน response ทำให้ client retry และสร้าง duplicate/ผิดสถานะ | Critical | `EXTERNAL_AUTHORIZATION_API_DECISION_LIFECYCLE.md`, `external_authorization_api_simulator.py` | v2 ใช้ idempotency replay, `COMMIT_UNKNOWN` และ reconciliation regression | real API ต้องมี durable idempotency, commit status query, bounded retry และ incident transcript |
| R-053 | Decision เก่าถูกใช้หลัง expiry/revocation หรือ poll จาก revision ที่ stale | Critical | v2 simulator expiry/revocation/stale polling tests | v2 block/expire/revoke และตรวจ known revision/hash | real client ต้อง invalidate cache, รับ revocation propagation และมี trusted server time |
| R-054 | Audit integrity failure ถูกตรวจพบแต่ state-changing operation ยังเดินต่อ | Critical | v2 simulator audit tamper/fail-stop regression | v2 เปลี่ยนเป็น `AUDIT_INTEGRITY_FAILURE` และ block commands | durable append-only store ต้อง verify-before-read, preserve incident snapshot และ require stop-authority recovery |
| R-055 | Production-readiness audit หรือจำนวนสถานะถูกตีความเป็น certification/authorization | Critical | `PRODUCTION_READINESS_EVIDENCE_AUDIT.md` | report ใช้ `NOT_PRODUCTION_READY`, แยก Implemented/Experimental/Unverified/Planned และตรึง authority false | ต้องมี named external decision, clinical governance, host/hardware and 10-gate evidence ก่อนเปลี่ยน claim |
| R-056 | Corrupted or replayed local simulator snapshot is restored as current authorization state | Critical | Wave A–D software control | snapshot SHA-256, package/manifest/scope/window binding, audit-chain verification and fail-closed restore regression | storage is in-memory/local software only; off-host encrypted retention, rollback detection and operator recovery approval remain unverified |
| R-057 | Local cache version is mistaken for distributed revocation propagation | Critical | Wave B simulation-only control | monotonic `cache_version`, decision revision and stale-cache rejection are returned in local responses | real external revocation stream, multi-process cache invalidation, offline expiry policy and trusted server clock remain external |
| R-058 | Simulator response-authenticity result is misread as a cryptographic signature verification | Critical | Wave D simulation-only denial control | simulator returns `trusted=false`, `SIMULATION_ONLY` and `BLOCK_UNTIL_EXTERNAL_SIGNATURE_AND_READBACK`; it rejects local authorization flags | real signed response, key ID, trust-chain validation, key custody and independent read-back remain unverified |
| R-059 | Chunk manifest validation is mistaken for complete transport or storage evidence | High | Wave C software control partially verified | bounded chunk count/size, contiguous sequence, per-chunk hash and `received=true` finalize checks | real upload transport, proxy limits, interrupted transfer recovery, durable storage and external receipt remain unverified |
| R-060 | Synthetic Wave 0 governance binding is treated as an external appointment, signature or custody decision | Critical | Wave D software control partially verified | constructor binds local governance state, validation snapshot and freeze record while requiring external verification pending | named external roles, signed scope, stop authority, custody and independent review remain external-unverified |
| R-061 | External reviewer receives metadata-only evidence without a per-test result or failure classification | High | Wave E evidence-v1 schema control | `test_run_id`, `test_case_id`, expected/actual result and failure class are now required; unknown/incomplete records reject | external owner must provide one record per T-01–T-12 and independent verifier must reproduce/read back the referenced artifacts |
| R-062 | Signed response is described but key, algorithm, signed payload and independent read-back are not bound to the evidence record | Critical | Wave E evidence-v1 schema control | `signature_ref`, `key_id`, `signature_algorithm`, `signed_payload_hash`, verification result and read-back ref are required for review-ready evidence | real trust chain, key custody, signature verification service and independent second-channel read-back remain external-unverified |
| R-063 | Uncertain commit or retry evidence cannot prove idempotent reconciliation | Critical | Wave E evidence-v1 schema control | idempotency hash, correlation ID, remote receipt and reconciliation result are required; `COMMIT_UNKNOWN` without reconciliation rejects | real endpoint must return durable receipt/status query and bounded retry transcript |
| R-064 | Timestamp/clock evidence is ambiguous or not ordered across external systems | High | Wave E evidence-v1 schema control | timezone-aware ordered timestamps, clock source, measured skew and time verification result are required | trusted external time source, skew policy and expiry/revocation propagation remain external-unverified |
| R-065 | Process-local rate-limit result is misinterpreted as multi-worker or multi-node enforcement | High | Wave E evidence-v1 topology fields | topology, worker count, limiter backend and quota scope are required; single-process worker count is bounded | real deployment topology and coordinated limiter/gateway behavior remain unverified |
| R-066 | Same role can stop, recover, prepare and independently verify a test without separation of duties | Critical | Wave E stop/recovery fields and role requirements | stopped/recovery roles and recovery evidence reference are required; external role appointments remain pending | external governance must enforce independent stop, recovery approval and verification identities |

Severity สะท้อน potential impact ไม่ใช่ probability. คำว่า “Implemented” หมายถึงมี code/test evidence สำหรับ control ที่ระบุเท่านั้น ไม่ได้หมายความว่า risk โดยรวมถูกกำจัด และคำว่า “pilot-ready foundation” ไม่ได้หมายความว่า clinical validation เสร็จแล้ว.

## Evidence pointers

| Evidence | Purpose |
|---|---|
| `test_residual_controls.py` | Rate-limit, replay, audit redaction, anchor และ idempotency evidence |
| `DEVICE_TRUST_BASELINE_REPORT.md` | Device Trust implementation, evidence and external validation gates |
| `test_device_trust.py` | Enforce-mode signed telemetry and lifecycle evidence |
| `test_device_trust_observe.py` | Observe-mode continuity evidence |
| `test_p0_hardening.py` | OIDC fail-closed, migration-first และ Alembic evidence |
| `test_p0_his_admission_contract.py` | Sandbox tokenization, TTL, revocation, idempotency and structured acknowledgment evidence |
| `power_loss_recovery_harness.py` | Software-only checkpoint/storage fault-injection evidence; physical gates remain unverified |
| `reliability_validation_result.json` | Software-only concurrent reliability result |
| `pilot_simulation_result.json` | Software-only 30-day simulation result |
| `OPERATIONS_RUNBOOK.md` | Operational controls and pilot procedures |
| `KEY_CUSTODY_PROVISIONING_CONTRACT.md` | Device Trust provisioning, custody, rotation, revocation and lost-device contract |
| `test_key_custody_contract.py` | Software-only dual-control and lifecycle evidence |
| `P1_004_EXTERNAL_ANCHOR_CONTRACT.md` | External anchor request/receipt contract and evidence boundary |
| `test_external_anchor_contract.py` | Software-only receipt, idempotency, deletion and tamper evidence |
| `test_external_anchor_fault_injection.py` | Software-only receipt mutation and provider-identity fault matrix |
| `FILE_ANCHOR_STORE_PRODUCTION_GAP_REVIEW.md` | FileAnchorStore production-readiness gap and post-hardening status |
| `test_file_anchor_store.py` | Local receipt, path, idempotency, readback and tamper evidence |
| `P1_005_CLINICAL_SHADOW_MODE_CONTRACT.md` | Shadow-mode governance and safety contract |
| `test_clinical_shadow_mode.py` | Software-only shadow activation, safe-label and stop/resume evidence |
| `test_clinical_shadow_mode_negative.py` | P1-005 raw-identity, context, timing, duplicate and metric-boundary negative matrix |
| `P1_005_CLINICAL_SHADOW_REVIEW.md` | Detailed P1-005 code/test review and clinical residual-risk statement |
| `P1_005_ZERO_PII_AND_NON_ACCURACY_METRICS.md` | Zero-PII field boundary and non-accuracy metric definitions |
| `P1_006_CLINICAL_VALIDATION_READINESS_PLAN.md` | Clinical validation prerequisites and external approval gates |
| `clinical_validation_readiness.py` | Software-only clinical validation preflight boundary |
| `test_clinical_validation_readiness.py` | Fail-closed P1-006 preflight regression |
| `GV10_INDEPENDENT_REVIEW_DOSSIER.md` | Independent-review evidence map and current external blockers |
| `GV10_SUBMISSION_CHECKLIST.md` | GV-10 redaction, hash, chain-of-custody and independent-review checklist |
| `gv10_evidence.py` | SHA-256, provenance, redaction and no-authorization evidence validator |
| `test_gv10_evidence.py` | GV-10 evidence mutation and claim-boundary regression |
| `P1_008_INDEPENDENT_REVIEW_OPERATIONS.md` | P1-008 lifecycle, finding and controlled-pilot boundary |
| `test_independent_review_operations.py` | Software-only review lifecycle, severity, traceability and no-authorization regression |
| `P2_004_REGISTRY_INDEX_HARDENING_PLAN.md` | P2-004 hardening findings and acceptance criteria |
| `evals/micro_rag/test_registry_index.py` | Registry lifecycle, snapshot, stale-index and atomic rebuild regression |
| `evals/micro_rag/test_registry_backed_evaluation.py` | Runner retrieval ownership and scope-bound provenance regression |
| `evals/micro_rag/test_response_adapter.py` | Hash, Thai support, citation scope and sensitive-output boundary regression |
| `evals/micro_rag/evidence/MICRO_RAG_V2_RERUN_EVIDENCE.md` | Model-specific rerun evidence and provider-limited interpretation |
| `P2_004_PERSISTENCE_OWNERSHIP_CONTRACT.md` | Persistence owner, custodian, retention, encryption and approval contract |
| `persistence_contract.py` | Fail-closed persistence policy validator and deterministic policy hash |
| `repeated_sample_evaluation.py` | Repeated-sample compatibility and provider-aware aggregation |
| `runtime_semantic_retrieval_readiness.py` | Fail-closed runtime readiness and no-authorization preflight |
| `P2_004_HARDENING_EVIDENCE.md` | P2-004 continuation evidence and readiness interpretation |
| `P2_004_REPEATED_SAMPLE_PROTOCOL.md` | Repeated-sample identity, minimum samples and decision matrix |
| `p2_004_review_decision.py` | Fail-closed repeated-sample decision validator |
| `controlled_pilot_handoff.py` | 10-gate handoff and no-authorization contract |
| `P2_004_EXTERNAL_REVIEW_COORDINATION_PACKAGE.md` | External-review evidence map and blocker visibility |
| `CONTROLLED_PILOT_OPERATIONS_GATE.md` | Operational states, promotion rules and evidence export contract |
| `CONTROLLED_PILOT_OPERATIONS_REVIEW_CHECKLIST.md` | Reviewer checklist and stop conditions |
| `controlled_pilot_operations.py` | Blocker, manifest and operational gate validation |
| `analyze_controlled_pilot_blockers.py` | Seven-blocker evidence-bounded status analysis |
| `EXTERNAL_AUTHORIZATION_UNBLOCK_PLAN.md` | Five-wave plan for external evidence and authorization |
| `WAVE_0_GOVERNANCE_CONTRACT.md` | Role, scope, test-window, stop-authority and freeze contract |
| `wave0_governance.py` | Wave 0 local validator and freeze simulation |
| `EXTERNAL_AUTHORIZATION_API_SIMULATION_CONTRACT.md` | Offline API handoff/status/audit contract and no-authorization boundary |
| `external_authorization_api_simulator.py` | Deterministic v2 simulator with Wave A–D hardening, decision lifecycle, snapshot/cache controls and audit fail-stop tests |
| `test_external_authorization_api_simulator.py` | Wave A–D concurrency, recovery, retry, chunk, governance and authenticity regression |
| `EXTERNAL_AUTHORIZATION_API_FAIL_CLOSED_GAP_REGISTER.md` | EA-001–EA-020 fail-closed gap register and remediation waves |
| `EXTERNAL_AUTHORIZATION_API_WAVE_A_D_HARDENING_PLAN.md` | Wave A–D software-vs-external disposition and Wave E handoff boundary |
| `EXTERNAL_AUTHORIZATION_API_DECISION_LIFECYCLE.md` | Expiry, revocation, stale polling, retry and partial commit design |
| `external_authorization_api_wave_e_evidence.py` | Strict Wave E per-test evidence record schema and dossier state machine; no-authorization boundary |
| `test_wave_e_evidence.py` | Wave E evidence-v1 and dossier state transition regression |
| `evals/micro_rag/evidence/wave-e-evidence-schema-v1.json` | Machine-readable Wave E record/state schema |
| `PRODUCTION_READINESS_EVIDENCE_AUDIT.md` | Evidence-bounded production-readiness classification and remaining blockers |


## Device Trust and provisioning roadmap risks

| ID | Risk | Severity | สถานะ | Control/evidence | Residual risk และ next gate |
|---|---|---:|---|---|---|
| R-019 | Unauthorized or counterfeit device enters the ward telemetry path | Critical | Planned Device Trust layer | Current device registration and sequence controls; manufacturer-authenticated provisioning is not yet implemented | Add asymmetric manufacturer certificate verification, device enrollment, revocation and hardware-in-loop tests |
| R-020 | Shared or hardcoded factory secret compromises the entire device fleet | Critical | Prevented by design decision; software custody contract in progress | `key_custody_contract.py` rejects private-key material, records public-key fingerprints only and requires explicit custody/attestation metadata | Validate secure-element/HSM key custody, manufacturer provisioning, rotation, revocation and lost-device drill |
| R-021 | Signed telemetry fails to cover all fields or canonicalization differs across device and Hub | High | Implemented software baseline | `device_trust.py` canonicalization, Ed25519 verification, field-mutation regression and `TelemetryPacket v1` contract; custody lifecycle is separately exercised | Requires cross-language device implementation test, firmware interoperability and hardware key custody |
| R-022 | Geofence or trust enforcement bricks a device and creates a patient-monitoring blind spot | Critical | Safety design principle; implementation pending | Fail-safe direction: alert, audit and degraded-trust/quarantine rather than automatic shutdown | Validate network-loss, location-error, offline-continuity and clinical escalation scenarios with governance approval |

The Device Trust layer is a strategic differentiator with an implemented software baseline and an open manufacturer/hardware roadmap, not a completed production security certification. The product may claim the current Ed25519 signed-telemetry and lifecycle controls with evidence boundaries, but it must not claim anti-spoofing 100%, tamper-proof evidence, clinical-ready operation or production-ready hardware security before the stated gates are closed.


## Ward workflow and integration risks

| ID | Risk | Severity | สถานะ | Control/evidence | Residual risk และ next gate |
|---|---|---:|---|---|---|
| R-023 | Raw HN/AN enters Hub through barcode, QR or HIS sync | Critical | Controlled at Hub boundary; external gateway pending | Pairing schema rejects common raw HN/AN formats; Hub accepts opaque token only | Validate the hospital Admission Gateway, tokenization authority, TTL, revocation and downstream mapping controls |
| R-024 | Accidental NFC tap resets an active device and creates a monitoring blind spot | Critical | Implemented software safety baseline | `RESET_PENDING`, visual confirmation, unresolved-incident freeze gate and workflow regression | Validate UI ergonomics, audio/visual confirmation, ward training and human-factors scenarios |
| R-025 | BLE/Gateway proxy signs or routes telemetry incorrectly | Critical | Prototype proxy boundary; unverified hardware trust | NFC is pointer-only; signed canonical telemetry and key ID are still checked by Hub | Establish proxy identity, attestation, key custody, replay policy, gateway failure handling and hardware-in-loop tests |
| R-026 | Hot-swap combines old and new device telemetry or sequence history | High | Implemented software session boundary | New `session_id`, opaque `handover_id`, routine close digest and per-device sequence guard | Validate real device reconnect, delayed packets, clock skew and operator recovery |
| R-027 | Routine close digest is mistaken for full incident evidence | High | Controlled by contract wording | Separate `SessionCloseDigest` from incident-linked `ForensicPackage` and explicit 10-minute incident window | Train operators, define retention, external anchor and evidence review procedure |


## Outside-in Ward Workflow risks

| ID | Risk | Severity | สถานะ | Control/evidence | Residual risk และ next gate |
|---|---|---:|---|---|---|
| R-028 | Outside-facing admission console exposes raw HN/AN or patient identity to Hub, logs, screen or visitors | Critical | Controlled software baseline; external Admission Gateway pending | Opaque-token validators, zero-PII audit test, loopback-only console, `OUTSIDE_IN_WARD_WORKFLOW.md` zoning/privacy boundary | Validate real HIS/Admission Gateway, screen placement, privacy filter, clipboard/screenshot policy, TTL and downstream mapping |
| R-029 | Outside console handoff is accepted visually but never committed by Fixed Hub | High | Implemented software baseline; HIS integration pending | Bed snapshot, `PREPARED`/`RESERVED`, idempotency key, pairing `COMMITTED`/`OCCUPIED`, cancellation and expiry regression | Validate real HIS/Admission Gateway, acknowledgement, retry/conflict behavior and network-failure test |
| R-030 | Physical console placement allows visitors to read data or access service ports | High | Design control | Controlled entrance alcove, outward-facing privacy angle, protected ports and short session timeout | Conduct site survey, privacy observation, physical tamper review and ward governance approval |
| R-031 | Roaming Tablet becomes an independent source of truth during Wi-Fi or Fixed Hub outage | Critical | Prevented by architecture; roaming implementation pending | Fixed Hub ownership, last-known-state banner, live-Hub requirement for destructive actions and revision/idempotency contract | Implement snapshot/command APIs, managed tablet identity, reconnect conflict tests and manual fallback |
| R-032 | Admission console, Fixed Hub and Roaming Tablet expose inconsistent bed/session states | High | Known integration risk; bed snapshot baseline implemented | Fixed Hub authoritative snapshot, bed availability revision, command/idempotency design and session state linkage | Validate multi-client concurrency, stale snapshot, duplicate handoff and real ward Wi-Fi behavior |

The Outside-in Ward Workflow is an operational differentiator with a software-verified bed availability and admission-preparation baseline, not evidence that a real HIS admission integration, physical privacy placement or clinical ward workflow has been validated. It must preserve the claims **Zero-PII by design**, **pilot-ready foundation** and **clinical validation pending**.


## Roaming Tablet risks

| ID | Risk | Severity | สถานะ | Control/evidence | Residual risk และ next gate |
|---|---|---:|---|---|---|
| R-033 | Roaming Tablet reads stale or inconsistent bed/session state | High | Implemented software baseline; network validation pending | Snapshot cursor/revision, freshness fields, `OFFLINE — LAST KNOWN STATE` policy and stale-revision `409` regression | Validate ward Wi-Fi roaming, clock drift, reconnect behavior and multi-client concurrency |
| R-034 | Duplicate roaming command causes duplicate acknowledgement, reset or admission action | Critical | Implemented software baseline | Durable `RoamingCommand`, command ID, idempotency key and replay regression | Validate crash boundary, multi-process deployment and command retention/cleanup |
| R-035 | Roaming Tablet performs destructive action without live Fixed Hub authority | Critical | Blocked by initial software policy | `RESET_CONFIRM` rejected from roaming path; destructive workflows remain Fixed Hub actions | Validate managed client enforcement, offline UI, operator training and clinical safety governance |
| R-036 | Unmanaged or compromised Tablet reads ward state or impersonates an operator | Critical | Experimental software scope baseline | Scope-based auth, tablet ID field, audit and non-PII snapshot; managed device identity not yet proven | Integrate OIDC, device certificate/MDM attestation, revocation and lost-tablet drill |
| R-037 | Tablet cache, screenshots or local logs retain patient identity or sensitive evidence | High | Controlled by contract; Android implementation pending | Snapshot excludes raw HN/AN/name and command audit redaction; mobile encrypted-cache implementation not complete | Validate BMAX kiosk/MDM policy, encrypted storage, screenshot/clipboard controls and wipe/revocation |

The roaming capability is a **software-verified pilot-ready foundation** for large-ward operations. It is not yet evidence of a validated Android deployment, hospital Wi-Fi service level, managed-device identity or clinical usability.
