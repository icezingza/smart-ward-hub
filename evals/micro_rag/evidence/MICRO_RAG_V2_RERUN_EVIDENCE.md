# Micro-RAG v2 Model Rerun Evidence Register

**Corpus:** `micro-rag-fixture-v2`

**Adapter:** `response-adapter-v1`

**Retrieval source:** `document-registry-v2/rebuildable-index-v2`

**Case count:** 8

**Scope:** synthetic operational and clinical-governance evidence only; no patient data; runtime authority `NONE`

## Evidence summary

| Run | Model and revision | Retrieval source | Result | Failure classification | Gate interpretation |
|---|---|---|---:|---|---|
| Pinned target, index-backed rerun | `gemini-2.5-flash`, revision `001` | registry/index v2; manifest and index hash recorded | 0/8 | 8 provider HTTP 429; 0 quality/adapter rejection | Provider-limited evidence; not a quality score; clean pinned rerun remains open |
| Alternate, index-backed rerun | `gemini-3-flash-preview`, revision `3-flash-preview-12-2025` | registry/index v2; manifest and index hash recorded | 6/8 | 2 provider HTTP 429; 0 quality/adapter rejection | Partial provider-limited evidence; six accepted cases are bounded model evidence only |
| Historical alternate baseline | `gemini-3-flash-preview`, revision `3-flash-preview-12-2025` | Earlier fixture-direct v2 run | 8/8 | No recorded provider failure | Valid only for that earlier retrieval path, prompt/hash set and model revision; not proof of runtime index deployment |

## Registry/index hardening evidence

The current runner now rebuilds a `DocumentRegistry` from the approved synthetic fixtures, derives a `RebuildableIndexAdapter`, and records `registry_manifest_hash`, `index_snapshot.index_hash`, `index_version`, retrieval configuration and adapter metadata in each model report. The runner uses a fixed synthetic approval epoch so compatible repeated samples can be compared deterministically. Current index-backed reports are:

- [`gemini-2.5-flash-v2-rerun-20260820.json`](gemini-2.5-flash-v2-rerun-20260820.json)
- [`gemini-3-flash-preview-v2-rerun-20260820-indexv2.json`](gemini-3-flash-preview-v2-rerun-20260820-indexv2.json)

The deterministic software tests also cover snapshot export/import, manifest hash preservation, tampered snapshot rejection, invalid lifecycle transition rejection, stale-index rejection, failed rebuild atomicity, Thai support tokens, cross-scope citation rejection and corrupted chunk-hash rejection.

Provider-aware aggregation reports are:

- [`gemini-2.5-flash-v2-repeated-aggregate-20260820.json`](gemini-2.5-flash-v2-repeated-aggregate-20260820.json): `INSUFFICIENT_SAMPLES`, one sample, zero quality denominator because all eight calls were provider-limited.
- [`gemini-3-flash-v2-repeated-aggregate-20260820.json`](gemini-3-flash-v2-repeated-aggregate-20260820.json): `INSUFFICIENT_SAMPLES`, one sample, six completed accepted cases, two provider-limited cases, quality pass rate `1.0` over a completed-case denominator of six.

Runtime readiness reports are:

- [`gemini-2.5-flash-v2-readiness-20260820.json`](gemini-2.5-flash-v2-readiness-20260820.json): `NOT_READY`; clinical and production authorization are false.
- [`gemini-3-flash-v2-readiness-20260820.json`](gemini-3-flash-v2-readiness-20260820.json): `NOT_READY`; clinical and production authorization are false.

## Interpretation

The current pinned `gemini-2.5-flash` run is **not a failed six-case quality evaluation**. All eight calls were blocked by provider HTTP 429, so the result is classified as `PROVIDER_LIMITED_REQUIRES_REVIEW`.

The current `gemini-3-flash-preview` run produced six accepted cases and two provider-limited cases. The six accepted responses passed the adapter boundary for the current registry/index-backed retrieval path; this does not establish a deployment hallucination rate, clinical safety, clinical accuracy, regulatory compliance, production readiness or runtime semantic-index readiness.

The earlier 8/8 alternate result remains bounded to its original fixture-direct retrieval path. It must not be conflated with the new registry/index-backed run.

P2-004 remains open for a clean pinned-target rerun, at least two compatible repeated samples per model/revision, operational persistence ownership/retention/access review, runtime semantic-retrieval deployment, human review and clinical retrieval governance. `READY_FOR_EXTERNAL_GOVERNANCE_REVIEW` is the maximum local preflight state and does not authorize clinical validation or production deployment.

## Files

- [`gemini-2.5-flash-v2-rerun-20260820.json`](gemini-2.5-flash-v2-rerun-20260820.json)
- [`gemini-3-flash-preview-v2-rerun-20260820-indexv2.json`](gemini-3-flash-preview-v2-rerun-20260820-indexv2.json)
- [`gemini-2.5-flash-v2-rerun-20260819.json`](gemini-2.5-flash-v2-rerun-20260819.json)
- [`gemini-3-flash-preview-v2-rerun-20260819.json`](gemini-3-flash-preview-v2-rerun-20260819.json)
- [`MICRO_RAG_MODEL_EVALUATION_REPORT.md`](../../MICRO_RAG_MODEL_EVALUATION_REPORT.md)
- [`MICRO_RAG_BILINGUAL_ADVERSARIAL_REPORT.md`](../../MICRO_RAG_BILINGUAL_ADVERSARIAL_REPORT.md)
- [`P2_004_PERSISTENCE_OWNERSHIP_CONTRACT.md`](../../P2_004_PERSISTENCE_OWNERSHIP_CONTRACT.md)
- [`P2_004_HARDENING_EVIDENCE.md`](../../P2_004_HARDENING_EVIDENCE.md)
