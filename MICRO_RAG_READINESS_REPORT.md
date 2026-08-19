# Smart Ward Hub — Micro-RAG Readiness Report

**วันที่:** 20 สิงหาคม 2026 (GMT+7)  
**สถานะ:** Deterministic evaluation baseline and model-agnostic response adapter implemented; Gemini model-specific baseline captured; runtime Micro-RAG pending

## Executive summary

The current Micro-RAG design is appropriately narrow for Smart Ward Hub: it retrieves approved operational and clinical-governance documents, preserves provenance and refuses unsupported or unsafe output. The deterministic suite passes all defined fixture cases. This does not mean that a vector store, embedding model, language model or clinical retrieval workflow has been implemented.

## What was verified

| Control | Result | Evidence |
|---|---|---|
| Approved-corpus admission | Passed | Only approved, current, non-PII fixtures admitted |
| Deprecated-policy exclusion | Passed | Legacy reset policy cannot displace current policy |
| Prompt-injection resistance | Passed | Untrusted imported instruction is not admitted |
| Citation provenance | Passed | Answerable operational response requires an admitted supporting citation |
| Unsupported destructive claim | Passed | Claim that tablet may confirm RESET is rejected |
| Unknown evidence/refusal | Passed | Uncovered hospital/clinical query produces no evidence |
| Clinical boundary | Passed | Triage/fall output remains decision support with human review pending |
| PII non-leakage | Passed | Restricted identity fixture cannot enter the corpus |
| Regression integration | Passed | Included in `run_all_tests.py`; offline adapter, hallucination and registry/index suites pass |
| Model-agnostic response adapter | Passed | Strict envelope, citation/provenance, refusal, safety and redaction tests pass |
| Thai/English and adversarial deterministic coverage | Passed | Corpus-v2 bilingual provenance and mixed-language injection cases pass |
| Approved registry/rebuildable index baseline | Passed | Approval, PII rejection, scope, stale, deprecation, revocation and atomic rebuild tests pass |
| Gemini model-specific baseline | Historical 5/5; current v2 alternate-model pass 8/8; pinned 2.5 rerun partial | `gemini-3-flash-preview` revision `3-flash-preview-12-2025` passed 8/8 through adapter; `gemini-2.5-flash` revision `001` current rerun passed 2/8 and six later calls returned HTTP 429 |

## Architecture decision

Do not add FAISS/Qdrant, PostgreSQL, Neo4j or Redis merely to satisfy the label “5-Tier Memory”. Start with an approved document registry and deterministic provenance contract. Add an embedding/vector index only after corpus size, latency, recall, retention and operational ownership are measured. Keep the index outside clinical source-of-truth state and make it rebuildable from approved documents.

The first safe production-like use case should be operational assistance: recovery runbooks, roaming workflow, admission console rules, evidence status and approved governance protocols. It should not answer diagnosis, treatment, dose, threshold or patient-specific disposition questions.

## Remaining gates

| Gate | Status | Required evidence |
|---|---|---|
| Runtime document registry and versioned ingestion | Software baseline implemented; persistence planned | Owner, hash, approval, expiry, removal and rebuild transcript |
| Deterministic rebuildable index adapter | Implemented baseline | Manifest hash, scope/language provenance, stale blocking, deletion and atomic rebuild tests |
| Semantic embedding/index adapter | Planned | Pinned model/index version, recall/precision evaluation, rebuild and deletion test |
| Model response adapter | Implemented baseline | Pinned model/version, prompt hash, response schema and redacted transcript contract |
| Model-specific hallucination evaluation | Alternate-model v2 pass captured; pinned target rerun pending | Gemini 3 Flash v2 passed 8/8 with redacted evidence; Gemini 2.5 v2 rerun is 2/8 due six HTTP 429 responses and needs a clean provider-window rerun |
| Human review and operational ownership | Planned | Reviewer, escalation, refusal handling and incident process |
| Clinical retrieval | Deferred | Separate clinical governance, validation and patient-data policy |
| Patient-specific retrieval | Not permitted in initial scope | Requires separate identity, consent, access and clinical governance design |

## Required model-specific evaluation envelope

A future model adapter must submit a response containing `answer`, `citations`, `retrieval_scope` and `evidence_status`, plus evaluation metadata: model ID/version, prompt/template hash, corpus revision, retrieval configuration, timestamp and redaction result. The evaluator must reject citation mismatch, unsupported claims, stale policy, PII leakage and clinical overreach.

## Claim boundary

The correct status is **Micro-RAG deterministic and registry/index baselines implemented; model-agnostic adapter implemented; historical Gemini 2.5 revision 001 baseline captured; current corpus-v2 eight-case evaluation passed for Gemini 3 Flash Preview; pinned Gemini 2.5 current-prompt rerun remains provider-limited; runtime semantic retrieval not implemented**. Passing these suites is evidence of contract behavior over synthetic fixtures only. It is not evidence of clinical accuracy, hallucination rate in a deployed model, regulatory compliance, production readiness or clinical readiness.
