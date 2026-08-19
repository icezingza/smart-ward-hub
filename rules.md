# Smart Ward Hub — Engineering and AI Rules

These rules are mandatory for code, documents, tests, agents, skills and deployment work.

## R-001 — Fixed Hub authority

Treat the Fixed Edge Hub as the authoritative local source of truth for telemetry, pairing, sessions, alerts, Device Trust, forensic evidence and destructive transitions. A roaming tablet, AI agent, vector store, scheduler or control room must not create a competing authority.

## R-002 — Zero-PII Edge

Never store or transmit raw HN, patient name, national ID, address, phone, free-text clinical note or identity mapping in Hub Core, project memory, control-plane metadata, skills, evidence or Git commits. Accept only opaque `patient_token`/`encounter_token` after Admission Gateway tokenization.

## R-003 — Locked telemetry contract

Use `TelemetryPacket v1` and its canonical signed serialization. Reject legacy identity fields, malformed payloads, duplicate sequence and out-of-order sequence. Do not introduce an alternate packet contract without an explicit versioned migration decision.

## R-004 — Fail closed

Missing authentication, invalid scope, invalid signature, stale revision, unsafe reset state, failed integrity check or missing required configuration must fail closed or enter a clearly visible degraded state. Never weaken a gate to make a test or demo pass.

## R-005 — Device Trust is not pairing

Device enrollment and key lifecycle prove device provenance. Pairing binds an enrolled device to an opaque session/bed context. NFC is only a pointer lookup and is never a root of trust.

## R-006 — Clinical safety is human-governed

Triage and fall signals are decision support. They are not diagnosis, treatment instruction or automatic disposition. Do not silently suppress, resolve, reinterpret or downgrade patient-safety alerts. Clinical threshold changes require clinical review and shadow-mode evidence.

## R-007 — Destructive actions require intent

Use `RESET_PENDING`, explicit Fixed Hub confirmation, incident freeze and appropriate session-close evidence. The initial roaming client must not issue destructive `RESET_CONFIRM`.

## R-008 — Offline truth is visible

When connectivity is absent or stale, show age and last-known state. Do not present cached data as current. A failed downstream sync retains local state and cannot trigger unsafe purge.

## R-009 — Evidence before claims

Label results `Implemented`, `Experimental`, `Planned`, `Not Found` or `Unverified`. Separate software simulation, real hardware, real hospital integration, external anchoring and clinical validation. Never claim `clinical-ready`, `production-ready`, `tamper-proof` or `100% compliant` from functional tests alone.

## R-010 — Secrets never enter artifacts

Do not commit `.env`, tokens, JWTs, private keys, TLS private keys, raw audit logs or runtime databases. Redact command output, reports and screenshots. Use key IDs/fingerprints rather than secret material.

## R-011 — External side effects need approval

Posting, exporting, applying, restoring, deleting, changing firewall/network exposure, rotating/revoking credentials or sending data to an external service requires explicit approval, allowlist, audit event, rollback and verification.

## R-012 — Idempotency and concurrency

Every retried mutation must have an idempotency key or deterministic deduplication. Use bounded memory, locks, revision checks and safe retry/backoff. Test duplicate, stale, out-of-order, crash and partial-failure behavior.

## R-013 — Prefer the smallest valid architecture

Do not add PostgreSQL, Redis, Neo4j, FAISS/Qdrant, Celery, multimodal emotion analytics or autonomous workers merely because they are fashionable. Introduce each capability only after a measured requirement, threat model, data boundary, rollback and acceptance test exist.

## R-014 — Documentation is executable context

Update the relevant PRD, design, architecture, task, rule, memory or skill contract when behavior changes. Keep source-of-truth links and avoid duplicating contradictory specifications.
