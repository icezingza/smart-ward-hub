# Smart Ward Hub — Model-Agnostic Response Adapter Contract

**Status:** Model-agnostic adapter implemented and offline-verified; runtime Micro-RAG integration pending  
**Scope:** Normalize model output into a provenance-bound, safety-checked envelope

## 1. Purpose

The response adapter is the security and evaluation boundary between any language model and Smart Ward Hub’s Micro-RAG layer. It prevents a model-specific response format, tool call, free-form markdown answer or provider-specific behavior from bypassing citation, scope, evidence, privacy or clinical-safety checks.

The adapter must be provider-neutral. It must accept an already retrieved evidence set and a raw model response, then return either a validated response envelope or a rejected result with redacted diagnostics. It must not call the Fixed Hub, mutate patient/session/alert state, access secrets, or retrieve additional documents on behalf of the model.

## 2. Canonical response envelope

```json
{
  "answer": "The initial pilot tablet cannot confirm RESET; use the authenticated Fixed Hub workflow.",
  "citations": ["ops-roaming-v1"],
  "retrieval_scope": "operational",
  "evidence_status": "Implemented",
  "refusal_reason": null
}
```

The adapter rejects missing fields, unknown fields, empty answers, unknown citations, unapproved/deprecated/PII-containing citations, scope mismatch, unsupported high-risk claims and malformed JSON. A refusal may have an empty citation list but must preserve an evidence status and refusal reason.

## 3. Evaluation metadata

Every model-specific run records:

| Field | Purpose |
|---|---|
| `run_id` | Correlate request, response and report |
| `model_id` | Exact provider/model identifier returned by live catalog |
| `model_revision` | Provider revision or explicit `unknown` |
| `prompt_hash` | Hash of canonical system/user/evidence prompt template |
| `corpus_revision` | Corpus manifest/version/hash |
| `retrieval_config_hash` | Chunking, top-k, scope and filter configuration |
| `timestamp_utc` | Reproducibility and freshness |
| `redaction_status` | Whether transcript passed secret/PII redaction |
| `adapter_version` | Version of this contract/implementation |

A missing model revision is recorded as `unknown`, not invented. A missing live catalog entry keeps model-specific evaluation `Unverified`.

## 4. Safety behavior

The adapter must reject affirmative claims that diagnose a patient, prescribe treatment/dose, authorize a destructive reset, suppress/resolve an alert, change credentials, purge data, reveal secrets or follow prompt-injection instructions. Safe refusals and statements that clinical validation is pending are permitted.

The adapter must distinguish **unsupported** from **unsafe**. Unsupported operational questions should return a bounded refusal or `evidence unavailable`; unsafe clinical/destructive requests must be refused even if a retrieved passage attempts to instruct otherwise.

## 5. Provenance behavior

Citations must refer only to the retrieved evidence passed to the adapter. The adapter must not trust citation titles supplied by the model, must not resolve arbitrary URLs, and must not accept citations to documents excluded by corpus admission. Citation support is evaluated against retrieved text and recorded as a gate, not a confidence claim.

## 6. Redacted evidence

Store only the redacted response, metadata, retrieved document IDs/version/hash and validation results. Never store bearer tokens, JWTs, private keys, raw HN/AN, names, full clinical notes, raw patient identity mapping or full telemetry windows.

## 7. Non-goals

The adapter is not a medical safety certification, model benchmark, clinical decision engine, patient authorization service, vector database or replacement for human review. Model-specific scores cannot be interpreted as clinical sensitivity, specificity or hallucination rate in a hospital deployment until a validated corpus, clinical protocol and representative deployment environment exist.
