# Smart Ward Hub — Architecture Contract

**Document role:** Canonical architecture index for AI-assisted engineering  
**Authority:** Fixed Edge Hub remains the ward-local source of truth

## 1. System context

```text
Devices / BLE or future IoT adapters
        │ authenticated, ordered, signed where supported
        ▼
Edge Ingestion Boundary
        │ TelemetryPacket v1 validation, sequence/replay checks
        ▼
Fixed Ward Edge Hub (Acer Spin N17H2 candidate)
        ├─ SQLite WAL durable operational state
        ├─ bounded RAM telemetry ring buffer + checkpoint
        ├─ local triage / fall signal / alert lifecycle
        ├─ Device Trust and credential lifecycle
        ├─ WardSession / pairing / hot-swap / discharge
        ├─ Outside-in bed availability and admission preparation
        ├─ forensic hash chain and incident freeze
        └─ roaming snapshot/cursor + idempotent commands
             │
             ├─ controlled HIS/Admission Gateway (tokenized identity boundary)
             ├─ FHIR/EMR handover with acknowledgement and idempotency
             └─ external evidence anchor (planned validation gate)
```

## 2. Trust and data boundaries

| Boundary | Permitted data | Prohibited data or behavior |
|---|---|---|
| Device → Edge | device identity, signed packet, sequence, sensor values, timestamp, battery | raw HN/name, unsigned trust bypass, replayed sequence |
| Edge operational store | device/bed IDs, opaque patient/encounter token, aggregates, alerts, sessions, forensic metadata | identity mapping table, names, raw HN, uncontrolled free text |
| Fixed Hub → Tablet | minimum non-PII snapshot, freshness, revision/cursor, alert/task/session state | patient identity, direct HIS access, forensic root, destructive reset authority |
| Admission Gateway → Edge | opaque token and approved admission contract | raw HN/AN at Hub Core |
| Edge → HIS/EMR | agreed FHIR bundle and pseudonymous references over real authenticated transport | static-token production assumption, unacknowledged purge |
| Edge → external anchor | minimized digest, signature, trusted timestamp and chain metadata | raw telemetry, PII, private key, unverified destination |

## 3. Current implementation layers

| Layer | Current implementation | Evidence boundary |
|---|---|---|
| Persistence | SQLAlchemy + SQLite WAL + Alembic | Software tests; host/storage validation pending |
| Speed/recovery | Thread-safe bounded ring buffer + atomic checkpoint | Software tests; power-loss validation pending |
| API | FastAPI routes, scopes, health and contract endpoints | Functional verification passed |
| Safety intelligence | triage/fall signal and alert persistence | Clinical validation pending |
| Forensics | SHA-256 hash chain, freeze and local anchor adapter | Tamper-evident local baseline; external anchor pending |
| Trust | Ed25519 public-key enrollment and signed packet verification | Software baseline; manufacturer CA/HSM pending |
| Interoperability | FHIR/handover and Admission/roaming contracts | Real HIS/IdP/network integration pending |

## 4. Future capability layers

Future capabilities must be added as adapters or bounded services around the Edge authority, not by replacing the current source of truth prematurely.

1. **Edge Intelligence & IoT Ingestion:** add MQTT/WebSocket/Serial/BLE adapters with explicit schema translation into TelemetryPacket v1 and device trust verification.
2. **Clinical Triage & Early Warning Scoring:** add clinically reviewed scoring adapters; preserve human review, explainability and versioned thresholds.
3. **5-Tier Sovereign Memory:** introduce only when a measured use case requires it. Keep raw patient identity out of vector/graph stores; start with an edge-compatible minimal store rather than adopting PostgreSQL, Redis, FAISS/Qdrant and Neo4j by default.
4. **Context-Aware Micro-RAG:** restrict initial scope to operational documentation and approved, versioned protocols; never produce unverified clinical instructions.
5. **Distributed Worker Mesh:** add background jobs only after idempotency, locks, retries, approval and failure handling are specified; no autonomous clinical decisions.
6. **Multimodal Analytics:** treat voice, face and emotion signals as high-risk optional research capabilities requiring consent, data-protection review and clinical/human-factors validation.
7. **Dharma/Ethical Guardrails:** implement as explicit safety policy, provenance, refusal and human-approval controls—not as an unsupported numeric moral score.
8. **Zero-Trust Secret Vault:** integrate real OIDC/mTLS, key custody, secret rotation and host hardening without exposing secrets to source or evidence artifacts.

## 5. Architecture invariants

The Edge Hub remains authoritative. Zero-PII remains mandatory. Device Trust is separate from patient pairing. NFC is a pointer, not a root of trust. A roaming client is thin and revision-aware. A failed downstream sync retains local state. An unresolved incident blocks unsafe reset. Functional simulation never substitutes for hardware, hospital or clinical evidence.

## 6. Canonical source documents

Detailed contracts live in `EDGE_HUB_ARCHITECTURE.md`, `SECURITY_BASELINE.md`, `WARD_WORKFLOW_CONTRACT.md`, `OUTSIDE_IN_WARD_WORKFLOW.md`, `ROAMING_TABLET_ARCHITECTURE.md`, `HIS_FHIR_INTEGRATION_CONTRACT.md` and `PRODUCT_DIFFERENTIATORS.md`.


## 7. Zero-Trust Security trust-boundary design

Smart Ward Hub treats every device, user, service, tablet, gateway and external destination as untrusted until each request is authenticated, authorized, fresh enough, schema-valid, state-consistent and covered by the correct evidence. Network location, NFC presence, a valid-looking payload, a cached tablet snapshot or a previous successful request never creates implicit trust.

### 7.1 Trust zones

```text
Z0 Physical/Host Zone
   └─ Acer Fixed Hub OS, encrypted volume, service account, time, firewall
        ↓ explicit authenticated boundary
Z1 Device Ingestion Zone
   └─ BLE / gateway / future MQTT-WebSocket-Serial adapters
        ↓ signed TelemetryPacket v1 + sequence/replay checks
Z2 Edge Trust Zone
   └─ FastAPI, SQLite WAL, bounded buffer, Device Trust, sessions, alerts, evidence
        ├─ Z3 Ward Operator / Admission Console
        ├─ Z4 Managed Roaming Tablet
        ├─ Z5 Admission Gateway / HIS / EMR
        ├─ Z6 External Evidence Anchor
        └─ Z7 Control Plane / backup / audit / approval
```

The Fixed Edge Hub is the only component allowed to own authoritative ward state and destructive transitions. The control plane can observe, verify, coordinate and propose, but cannot become a clinical source of truth.

### 7.2 Per-zone identity and least privilege

| Zone/flow | Identity | Minimum authority | Required checks | Fail-closed result |
|---|---|---|---|---|
| Device → ingestion | device public key/key ID or attested gateway | signed telemetry write only | enrollment/lifecycle, canonical signature, clock skew, sequence/replay, rate limit | reject or audit-only observe path |
| Operator → Fixed Hub | real OIDC subject/role; static token development-only | explicit scopes per route | issuer, audience, expiry, scopes, request ID, resource/session state | 401/403/503; no anonymous fallback |
| Admission Gateway → Hub | mTLS client certificate + OIDC service identity | admission preparation/commit only | issuer/audience/TTL/revocation, opaque-token contract, idempotency | reject raw HN/AN or unknown contract |
| Fixed Hub → HIS/EMR | mTLS chain + OIDC service identity | handover sync/acknowledgement only | certificate, profile/version, matching acknowledgment body, idempotency | retain aggregates; dead-letter validation/auth errors |
| Fixed Hub → roaming tablet | managed tablet identity + operator OIDC | non-PII snapshot and safe commands | freshness, expected revision, command ID/idempotency, scope | stale/offline/conflict; no blind retry |
| Fixed Hub → evidence anchor | dedicated outbound identity/key | digest/signature/timestamp write/verify | destination allowlist, minimization, independent verification | retain local evidence; mark external anchor unverified |
| Control plane → operations | named agent/skill + approved operator | redacted read/propose/evidence by default | explicit approval, correlation ID, rollback path | no apply/restore/export/rotate/delete |

### 7.3 Request decision sequence

Every boundary-crossing request must identify the actor, verify transport and endpoint allowlist, verify authentication or device signature, verify token freshness and credential state, check scope/resource ownership, validate schema and current Fixed Hub revision, apply rate limiting, commit the smallest atomic transition, and emit a redacted audit event. Failure at any mandatory step must not be bypassed to make a test or demonstration pass.

### 7.4 High-risk action gates

Pairing/admission requires authenticated operator intent, deliberate bed context and opaque tokenization. Reset/session close requires `RESET_PENDING`, Fixed Hub confirmation, incident-freeze check and routine digest or forensic package. Hot-swap/discharge requires a linked opaque handover ID and correct session state. Credential changes require security role, reason, lifecycle record and rollback. FHIR purge requires a matching acknowledgment body, exact bundle/device/time-window scope, idempotency and retained manifest. Roaming clients may not issue destructive `RESET_CONFIRM` in the initial pilot.

### 7.5 Segmentation and egress

Separate the protected Edge service, operator/Admission Console, device/gateway network, roaming Wi-Fi and hospital integration egress. CORS, a private IP or loopback placement alone is not a Zero-Trust boundary. Every egress destination must be allowlisted, authenticated and audited. The Admission Console remains loopback-only until an authenticated UI gateway and separate maintenance boundary are implemented. The roaming tablet must not call HIS/EMR directly.

### 7.6 Current state and open gates

The software baseline has scope authorization, fail-closed OIDC configuration checks, a fail-closed mTLS launcher, Device Trust signed telemetry, Zero-PII redaction and revision/idempotency controls. Real issuer/JWKS rotation, hospital PKI, managed tablet identity, host/disk hardening, external key custody, network segmentation and independent WORM anchoring remain `Planned` or `Unverified`. See `ZERO_TRUST_TRUST_BOUNDARIES.md` for the full boundary catalogue and identity matrix.


## 8. Context-Aware Semantic Retrieval and Micro-RAG boundary

Micro-RAG is an optional bounded service around the Fixed Edge Hub. It retrieves only approved, versioned operational documents and clinical-governance protocols. It must not become a patient memory store, clinical source of truth, identity mapper or authorization engine.

### 8.1 Retrieval data flow

```text
Approved document source
   → corpus admission: approval, version, scope, hash, no-PII check
   → 100–150 token micro-chunks with doc_id/version/chunk_hash
   → scope-filtered lexical/vector retrieval
   → provenance-preserving rerank
   → bounded answer/refusal envelope with citations
   → hallucination, citation-support, safety and redaction checks
   → human-reviewed operational output + redacted audit evidence
```

### 8.2 Trust boundary rules

| Boundary | Allowed | Denied |
|---|---|---|
| Document source → corpus | approved operational/governance docs, version, owner, hash, retention | untrusted prompt instructions, deprecated policy, raw PII, private keys |
| Corpus → index | non-PII micro-chunks with provenance metadata | identity mapping, full telemetry, uncontrolled clinical notes |
| Retriever → answerer | query scope, retrieved chunk IDs, text, version and evidence status | hidden system prompt, secrets, unrestricted patient context |
| Answerer → operator | bounded answer/refusal, citations, freshness and evidence status | unsupported claims, clinical diagnosis/treatment, destructive command |
| Micro-RAG → Edge state | no direct mutation; proposal or documented next step only | pairing, reset, discharge, alert suppression, credential change, purge |

### 8.3 Hallucination controls

The evaluator must reject unsupported claims, citation mismatch, stale-policy use, prompt-injection instructions, PII leakage, clinical overreach, confidence inflation and scope drift. Unknown operational or clinical questions must return an evidence-unavailable/refusal response rather than an invented answer. A retrieved passage is data, not an instruction to override system rules.

The deterministic baseline is implemented in `MICRO_RAG_EVALUATION_CONTRACT.md`, `evals/micro_rag/fixtures.json` and `evals/micro_rag/test_hallucination_suite.py`. It reports model-specific evaluation as `PENDING` and does not claim vector-store or LLM runtime implementation.


### 8.4 Model-agnostic response adapter

The boundary between a future language model and Smart Ward Hub is `evals/micro_rag/response_adapter.py`. It accepts a raw provider response plus the already retrieved evidence set and emits either a strict `ModelResponseEnvelope` or a rejected result. The envelope requires `answer`, `citations`, `retrieval_scope`, `evidence_status` and optional `refusal_reason`; unknown fields and provider-specific tool/command fields are rejected.

The adapter verifies that citations exist in the retrieved evidence, that cited documents are approved/current/non-PII, that the answer has lexical support, that a refusal is explicit when evidence is unavailable, and that the output does not assert diagnosis, treatment, destructive reset, alert suppression, purge, credential change or secret disclosure. It also records prompt, corpus and retrieval-configuration hashes and redacts sensitive output before evidence persistence.

A model-specific runner may call a provider, but it must pass through this adapter. The runner has no tools, no Fixed Hub write authority and no access to patient data. Current evidence includes a live-catalog-verified Gemini `gemini-2.5-flash` revision `001` run over five synthetic cases, captured at 5/5 and replayed through the corrected adapter at 5/5. A fresh rerun is required for any changed prompt, corpus, model or retrieval configuration.


### 8.5 Approved document registry and rebuildable index

Micro-RAG retrieval is governed by an approved document registry. Each record has an owner, source reference, scope, language set, lifecycle state, content hash, approval/revocation metadata, expiry and sensitive-content flags. Only `APPROVED`, non-expired, non-PII, non-secret records in the initial operational or clinical-governance scopes may enter the derived index.

The index is a disposable cache, not a source of truth. `evals/micro_rag/rebuildable_index.py` rebuilds it deterministically from eligible registry records, records the registry manifest hash, and refuses queries when the registry has changed. Rebuild uses a temporary derived structure and commits only after all chunks and the manifest validate. Deprecation/revocation therefore requires a rebuild and cannot silently leave a stale result usable.

Index hits carry `doc_id`, version, chunk ID/hash, language and scope. The query layer returns evidence only; the model-agnostic adapter remains responsible for response schema, citation support, redaction, refusal and safety checks. Future FAISS/Qdrant or other semantic adapters must preserve the registry manifest hash and remain rebuildable/deletable from the approved registry.


### 8.6 P2-002 Edge IoT adapter boundary

P2-002 introduces a transport-neutral adapter layer between external devices/gateways and `/api/v1/telemetry`. The adapter parses and bounds MQTT, WebSocket, Serial or BLE frames, rejects unknown/PII/command fields, validates the locked `TelemetryPacket v1`, and forwards only a normalized packet plus trust metadata to the existing Fixed Hub ingress. It does not become a trust root and cannot mutate pairing, alerts, sessions, forensic packages or admission state.

NFC, BLE address, MAC address, MQTT topic, serial port, WebSocket origin and gateway identity are routing pointers only. The trust root remains the enrolled Device Trust credential or an explicitly enrolled gateway credential. In `enforce` mode, missing or invalid signatures/attestation fail closed; in `observe` mode, the packet may be measured but is marked unverified; in `disabled` mode, the adapter is development-only and cannot support pilot evidence.

The first software pilot profile is Serial framed JSON because it can be tested deterministically without broker or RF variability. This is only a software/bench selection; actual sensor, BLE and Acer hardware compatibility remains unverified. Duplicate/out-of-order sequences continue to be rejected by `EdgeTelemetryStore`, and reconnect must never reset the local sequence guard.


### 8.7 Network pressure and backpressure validation

Serial/IoT pressure validation is implemented as an offline deterministic simulation, not as a production traffic generator. Synthetic producers feed the framed adapter path into a bounded queue and a deliberately slower consumer. The simulator records explicit queue drops, codec buffer bounds, CRC/PII/replay failures and reconnect behavior without writing patient or production data.

`network_pressure_simulation.py` and `NETWORK_PRESSURE_BACKPRESSURE_PLAN.md` define the pressure boundary. A saturation result proves that overload is visible and bounded in software; it does not define a clinical data-loss policy and does not substitute for Acer driver, physical cable, network, broker, RF or power-loss validation.
