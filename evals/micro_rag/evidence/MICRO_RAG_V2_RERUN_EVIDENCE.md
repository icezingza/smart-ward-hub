# Micro-RAG v2 Model Rerun Evidence Register

**Corpus:** `micro-rag-fixture-v2`
**Adapter:** `response-adapter-v1`
**Case count:** 8
**Scope:** synthetic operational and clinical-governance evidence only; no patient data; runtime authority `NONE`

## Evidence summary

| Run | Model and revision | Catalog | Result | Gate interpretation |
|---|---|---|---:|---|
| Pinned target rerun | `gemini-2.5-flash`, revision `001` | Verified live before run | 2/8; six later provider calls returned HTTP 429 | Partial provider-limited evidence; not a six-case quality score; clean rerun remains open |
| Alternate current run | `gemini-3-flash-preview`, revision `3-flash-preview-12-2025` | Verified live before run | 8/8 through adapter | Valid current v2 model-specific evidence for this model/revision only |

The successful alternate-model report records `model_catalog_verified=true`, `redaction_status=PASS` on every case, no adapter violations and `runtime_authority=NONE`. It covers answerable operational retrieval, unknown clinical refusal, recovery policy, clinical overreach boundary, English prompt-injection resistance, bilingual Thai/English policy, bilingual adversarial injection and mixed-language destructive-claim rejection.

## Interpretation

The `gemini-3-flash-preview` 8/8 result is bounded evidence that the current response adapter accepted all eight outputs for one pinned model/revision and corpus/prompt hash set. It does **not** establish a deployment hallucination rate, clinical safety, clinical accuracy, regulatory compliance, production readiness or runtime Micro-RAG readiness.

The historical `gemini-2.5-flash` five-case 5/5 result remains valid only for its original prompt and `micro-rag-fixture-v1`. The current pinned-target v2 run must not be marked as passed because six of eight calls were blocked by provider HTTP 429. The P2-004 gate remains open for a clean pinned-target run, repeated-sample evaluation, persistence/ownership review and runtime semantic-retrieval validation.

## Files

- [`gemini-2.5-flash-v2-rerun-20260819.json`](gemini-2.5-flash-v2-rerun-20260819.json)
- [`gemini-3-flash-preview-v2-rerun-20260819.json`](gemini-3-flash-preview-v2-rerun-20260819.json)
- [`MICRO_RAG_MODEL_EVALUATION_REPORT.md`](../../MICRO_RAG_MODEL_EVALUATION_REPORT.md)
- [`MICRO_RAG_BILINGUAL_ADVERSARIAL_REPORT.md`](../../MICRO_RAG_BILINGUAL_ADVERSARIAL_REPORT.md)
