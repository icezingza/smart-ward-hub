# P2-004 Evidence Sufficiency & Provenance Readiness Report

**Date:** 22 August 2026
**Status:** `VERIFIED — SOFTWARE GATE BLOCKED BY INSUFFICIENT EXTERNAL EVALUATION EVIDENCE`
**Decision:** `P2_004_EVIDENCE_SUFFICIENCY_BLOCKED`
**Scope:** Local validation of Micro-RAG repeated-sample aggregate, registry/index provenance, release-freeze binding and claim suppression

## 1. Executive summary

A new read-only, local-only sufficiency gate now validates whether the current Micro-RAG evaluation aggregate may support a review handoff. The gate does not call a model provider, transmit data, mutate runtime state, or promote authorization. It verifies the aggregate schema, expected repeated-sample status, case-count completeness, registry/index provenance hashes, release-freeze membership/hash, redaction and locked authorization boundary.

The current evidence is correctly blocked. The aggregate contains **one sample** while the protocol requires at least two compatible samples, and it contains two provider-limited cases. The existing `quality_pass_rate=1.0` is therefore not promoted to an external-review or production claim. This is an intentional fail-closed result, not a model-quality failure classification.

## 2. Evidence results

| Control | Result | Evidence |
|---|---|---|
| Aggregate schema and suite | Passed | `micro-rag-repeated-sample-aggregation-v1` and required fields validated |
| Freeze membership/hash | Passed | Aggregate is listed in `release-candidate-freeze-20260820.json`; SHA-256 matches |
| Registry/index provenance | Passed | `document-registry-v2/rebuildable-index-v2`; registry and index hashes are valid |
| Case-count structure | Passed | Current aggregate has 1 sample × 8 cases = 8 case results |
| Minimum compatible samples | Blocked | `sample_count=1`, `minimum_samples=2` |
| Provider/runtime/quality blocker gate | Blocked | `provider_limited_cases=2`; runtime failures `0`; quality rejections `0` |
| Quality-claim suppression | Passed | `quality_claim_suppressed_until_sufficient=true` |
| Redaction | Passed | `redaction_pass=true`, `redaction_verified=true` |
| Authorization boundary | Locked | `external_authority=NONE`, `runtime_authority=NONE`, production/clinical authorization false |

## 3. Current aggregate facts

The freeze-bound aggregate is `evals/micro_rag/evidence/gemini-3-flash-v2-repeated-aggregate-20260820.json`. It reports model `gemini-3-flash-preview`, revision `3-flash-preview-12-2025`, corpus `micro-rag-fixture-v2`, adapter `response-adapter-v1`, retrieval source `document-registry-v2/rebuildable-index-v2`, `sample_count=1`, `total_case_results=8`, `provider_limited_cases=2`, `runtime_or_adapter_failures=0`, `quality_rejections=0`, `quality_pass_rate=1.0` and aggregate status `INSUFFICIENT_SAMPLES`.

The sufficiency snapshot is `evals/micro_rag/evidence/p2-004-evidence-sufficiency-local.json`. Its remediation codes are `MINIMUM_COMPATIBLE_SAMPLES_MISSING` and `EVALUATION_BLOCKER_PRESENT`; `external_review_eligible=false`, `production_ready=false`, `clinical_validation=PENDING`, `hardware_evidence=UNVERIFIED` and `read_only=true`.

## 4. Control design

The evaluator derives an expected aggregate status from bounded counts before accepting the declared status. It rejects incomplete or malformed counts, mismatched case totals, provider/runtime/quality blockers, invalid registry/index hashes, incorrect retrieval source, freeze hash mismatch, raw identity/secret markers and authorization-boundary mutation. A complete clean repeated set can reach `P2_004_EVIDENCE_SUFFICIENCY_READY_FOR_REVIEW`, but that decision only means locally structured evidence is eligible for human/external review; it cannot authorize external execution, clinical validation or production deployment.

The focused suite covers the current blocked path, a clean synthetic two-sample path, provider-limited evidence, malformed counts/status conflict, provenance and raw-identity mutation, and freeze/hash/authorization mutation. The phase-end gate additionally checks no network/provider/scheduler imports, exporter round-trip, redaction, private-key exclusion, no-self-authorization and `git diff --check`.

## 5. Required next evidence

To clear this specific sufficiency blocker, an approved non-production evaluation window must produce at least two compatible reports for the same model revision, corpus revision, adapter version, retrieval source, registry manifest and index snapshot. Each report must contain the expected eight cases and must not be provider-limited, runtime/adapter-failed or quality-rejected. The rerun must remain redacted, independently reviewable and bound to the current freeze/provenance lineage.

This repository can prepare and validate the intake contract, but it cannot create the external provider window, appoint a reviewer, approve persistence, establish clinical governance or authorize production. Those remain external gates.

> This control supports the claim **controlled production prototype with an evidence-sufficiency guard**. It does not support claims of production-ready, clinical-ready, tamper-proof, or 100% HIPAA/PDPA compliance.

## 6. Files and verification

| Item | Path / value |
|---|---|
| Evaluator | `p2_004_evidence_sufficiency.py` |
| Exporter | `export_p2_004_evidence_sufficiency.py` |
| Focused tests | `test_p2_004_evidence_sufficiency.py` — 6 passed |
| Phase-end gate | `test_p2_004_evidence_sufficiency_phase_end_hardening.py` — passed |
| Master integration | `run_all_tests.py` |
| Aggregate input | `evals/micro_rag/evidence/gemini-3-flash-v2-repeated-aggregate-20260820.json` |
| Sufficiency snapshot | `evals/micro_rag/evidence/p2-004-evidence-sufficiency-local.json` |
| Feature commit | `ccdd80ef1bbadedc1f58df9d2d0224d9b862d62e` |
| Feature freeze source | `ccdd80ef1bbadedc1f58df9d2d0224d9b862d62e` |

The evidence snapshot was generated against a passing freeze and then committed separately. A new freeze refresh is required after this report and traceability updates, followed by master regression, runtime-artifact cleanup and final alignment verification.
