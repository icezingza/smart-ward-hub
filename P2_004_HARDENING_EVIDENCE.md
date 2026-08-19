# P2-004 — Registry/Index Hardening & Model Rerun Evidence

**สถานะ:** software hardening verified; model evidence provider-limited; runtime semantic retrieval and clinical retrieval governance pending

## 1. Software hardening result

| Control | Evidence | Result | Boundary |
|---|---|---|---|
| Approved document lifecycle | `DocumentRegistry v2` + transition tests | Passed | Software registry contract only |
| Registry persistence | Deterministic JSON snapshot export/import, snapshot hash and manifest hash | Passed | Not a production authority or retention decision |
| Rebuildable index | `RebuildableIndexAdapter v2` snapshot/index hash, chunk hash and registry binding | Passed | Derived index; registry remains authoritative |
| Stale/failed rebuild behavior | stale registry rejection and atomic failed rebuild test | Passed | Single-process software behavior |
| Adapter provenance | evidence chunk hash, eligibility, citation scope and timezone-aware metadata | Passed | Does not validate external corpus ownership |
| Bilingual support | Thai bigram + English token support regression | Passed | Synthetic corpus only |
| Runner retrieval ownership | model runner uses registry-backed rebuilt index and records hashes | Passed | Runtime deployment not completed |

## 2. Model-specific rerun results

| Model/revision | Path | Result | Failure summary | Interpretation |
|---|---|---:|---|---|
| `gemini-2.5-flash` / `001` | registry/index v2 | 0/8 | 8 provider HTTP 429; 0 quality/adapter rejection | `PROVIDER_LIMITED_REQUIRES_REVIEW`; not a quality score |
| `gemini-3-flash-preview` / `3-flash-preview-12-2025` | registry/index v2 | 6/8 | 2 provider HTTP 429; 0 quality/adapter rejection | Partial bounded evidence; clean repeated run required |
| Historical Gemini 3 run | fixture-direct v2 | 8/8 | no recorded provider failure | Not interchangeable with current index-backed path |

Every model report records catalog verification, model revision, prompt hash, retrieval configuration hash, registry manifest hash or index snapshot metadata, `redaction_status=PASS` for completed cases, `runtime_authority=NONE` and `clinical_validity=PENDING`.

## 3. Gate decision

P2-004 remains **In Progress**. The software registry/index acceptance criteria are met for the current deterministic fixture path, but the overall P2-004 gate remains open because the pinned target has not completed a clean provider-window run, repeated samples are absent, runtime persistence ownership/retention is not approved, human review is not complete and clinical retrieval is outside the validated boundary.

## 4. Residual risks

The main residual risks are provider rate limiting being mistaken for model quality, registry/index snapshots being mistaken for production source of truth, lack of runtime semantic-index deployment, and lack of clinical governance for retrieval content. These are recorded as R-040 and R-041 in `RISK_REGISTER.md`.

## 5. Product claim boundary

The result supports the terms **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed** and **pilot-ready foundation**. It does not support `clinical-ready`, `production-ready`, `tamper-proof`, `HIPAA/PDPA compliant 100%`, clinical accuracy, clinical validation or external gate closure.
