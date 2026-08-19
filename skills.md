# Smart Ward Hub — Skill Map

**Document role:** Connect the project-local operational skills with the product’s future sovereign capability skills

## 1. Two skill planes

Smart Ward Hub uses two complementary skill planes:

1. **Sovereign Operations & Assurance Skills** govern how work is routed, approved, deployed, backed up, audited and evidenced.
2. **Sovereign Clinical-Edge Capability Skills** describe product capabilities that may be implemented as bounded adapters or services after their evidence gates are satisfied.

The first plane protects the second. Neither plane may bypass Fixed Hub authority, Zero-PII, Device Trust or clinical review.

## 2. Sovereign Operations & Assurance Skills

| Skill | Project-local path | Use |
|---|---|---|
| Host preparation | `.claude/skills/create-vps/SKILL.md` | Fixed Hub host, firewall, operator and prerequisites |
| Setup/upgrade | `.claude/skills/setup-control-room/SKILL.md` | Dry-run, apply gates, migration, manifest and rollback |
| Task routing | `.claude/skills/agent-task-router/SKILL.md` | Risk/capability/dependency routing |
| Registry | `.claude/skills/agent-registry-manager/SKILL.md` | Service, agent, adapter and Device Trust metadata |
| Backup | `.claude/skills/agent-backup-manager/SKILL.md` | WAL-aware backup, checksum, retention and restore |
| Security audit | `.claude/skills/agent-security-auditor/SKILL.md` | Auth, Zero-PII, Device Trust, input and residual-risk audit |
| Scheduler | `.claude/skills/agent-team-cron-planner/SKILL.md` | Health, backup, audit and evidence jobs; no clinical automation |
| Control room | `.claude/skills/agent-control-room/SKILL.md` | Status, approvals, incidents, evidence and rollback |

## 3. Sovereign Clinical-Edge Capability Skills

| Capability | Initial bounded implementation | Gate before expansion |
|---|---|---|
| Edge Intelligence & IoT Ingestion | Translate MQTT/WebSocket/Serial/BLE into TelemetryPacket v1 through authenticated adapters | Device Trust, adapter tests, latency/packet-loss evidence and hardware bench |
| 5-Tier Sovereign Memory & Reasoning Graph | Start with the existing SQLite/aggregates/forensic lineage; add stores only for measured needs | Data classification, retention, encryption, query isolation, backup/restore and no-PII review |
| Clinical Triage & Early Warning Scoring | Versioned local decision-support adapter with explainable output | Clinical reviewer, shadow mode, threshold governance, false-positive/negative evaluation |
| Multimodal Sensory & Emotion Analytics | Research-only optional pipeline, not pilot default | Consent, privacy impact review, model validation, clinical review and strict data minimization |
| Dharma/Ethical Alignment & Safety Guardrails | Explicit rules, provenance, refusal, human approval and fail-closed behavior | Safety test suite and governance review; avoid unsupported moral scoring |
| Zero-Trust Security, RLS & Secret Vault | Real OIDC/mTLS, key custody, secret rotation and host hardening around Edge | Hospital IdP/PKI, rotation/revocation, least privilege and recovery evidence |
| Autonomous Scheduler & Distributed Worker Mesh | Idempotent non-clinical health/backup/audit workers | Locks, retries, failure injection, rollback and explicit side-effect approval |
| Context-Aware Semantic Retrieval & Micro-RAG | Narrow retrieval over approved operational documents and protocols | Corpus provenance, redaction, retrieval evaluation, refusal and citation checks |

## 4. Skill invocation rules

Before invoking a capability skill, route the task through the operations plane. The route must identify data class, safety risk, authority, dependency, approval and evidence. Capability skills may propose or compute; they may not silently alter clinical state, patient identity, trust credentials or forensic evidence.

## 5. Recommended implementation order

Implement and validate Edge adapters and real identity/transport first. Then complete hardware/power/recovery and clinical shadow-mode gates. Add a narrowly scoped scoring adapter only after clinical review. Add worker runtime and operational retrieval after idempotency and provenance are stable. Defer multimodal emotion analytics and large distributed memory stacks until there is a validated use case, consent/governance basis and evidence plan.

## 6. Anti-hype rule

A skill name is not evidence that the capability exists. Use the project status vocabulary and record a reproducible acceptance test before describing a capability as implemented.


## 7. Context-Aware Semantic Retrieval & Micro-RAG boundary

Micro-RAG is a **bounded retrieval capability over approved operational and governance documents**, not a clinical memory and not a second source of patient truth. The initial corpus must be versioned, approved, non-PII, provenance-preserving and independently removable. Deprecated documents, untrusted imported notes, raw HN/AN, names, clinical free text, private credentials and full telemetry windows are excluded before chunking or indexing.

The intended pipeline is:

```text
approved corpus admission
  → metadata and PII filter
  → 100–150 token micro-chunk with doc_id/version/hash
  → lexical/vector retrieval with scope filter
  → provenance-preserving rerank
  → bounded answer/refusal envelope
  → citation-support and safety evaluation
  → redacted audit evidence
```

A future answer must carry `citations`, `retrieval_scope` and `evidence_status`. The system must refuse or mark evidence unavailable when the answer is unsupported, the citation is missing/mismatched, the source is stale/unapproved, the question requests a clinical instruction without an approved governance source, or the content attempts prompt injection. Retrieval output is evidence for a human-reviewed answer; it is not authorization to change sessions, alerts, credentials, admission state or forensic evidence.

The current repository contains `MICRO_RAG_EVALUATION_CONTRACT.md`, a synthetic corpus, `evals/micro_rag/test_hallucination_suite.py`, `evals/micro_rag/response_adapter.py` and `evals/micro_rag/run_gemini_evaluation.py`. The deterministic hallucination/provenance baseline and model-agnostic response adapter are implemented. A bounded Gemini `gemini-2.5-flash` revision `001` evaluation was captured at 5/5 and replayed through the corrected adapter at 5/5. Runtime retrieval remains unimplemented, and any new model or prompt revision must pin model/version, prompt/template hash, corpus revision, retrieval configuration and redacted transcript before a capability claim.


### 8.6 Approved document registry and rebuildable index skill

The registry is the authority for document eligibility; the index is a rebuildable derived cache. The implementation baseline is `evals/micro_rag/document_registry.py` plus `evals/micro_rag/rebuildable_index.py`. The registry rejects PII/secret-bearing content, requires explicit approval, tracks lifecycle states and content hashes, and supports deprecation/revocation. The index carries registry-manifest provenance, scope/language metadata and deterministic chunk hashes. A registry mutation makes the index stale and blocks retrieval until rebuild. This skill must not ingest patient-specific data, raw HN/AN, clinical free text, secrets or telemetry windows.

The current deterministic corpus revision is `micro-rag-fixture-v2`, with Thai/English operational evidence and bilingual adversarial fixtures. Registry/index tests cover approval, PII rejection, bilingual retrieval, scope isolation, deterministic rebuild, stale blocking, deprecation, revocation and failed-rebuild atomicity.


### 8.7 Edge IoT adapter skill

P2-002 is a transport-neutral data-plane skill. `edge_iot_adapters.py` provides MQTT, WebSocket, Serial and BLE adapter profiles that normalize bounded frames into `TelemetryPacket v1`. The adapter validates source identity, field allowlists, frame size, PII/secret/command rejection and signature-envelope presence, while Fixed Hub remains responsible for Device Trust verification, active pairing, sequence guard and durable/clinical side effects.

The first software pilot gate is the Serial profile. The adapter test suite proves translation, malformed input rejection, missing signature rejection, identity mismatch, bounded frame size, Device Trust canonical signature compatibility and replay protection. Hardware, broker, RF, serial-driver, BLE pairing and gateway-attestation evidence remain `Unverified` until bench validation.
