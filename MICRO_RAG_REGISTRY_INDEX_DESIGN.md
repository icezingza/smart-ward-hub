# Smart Ward Hub — Approved Document Registry and Rebuildable Index Design

**Status:** Design and local software baseline  
**Scope:** Operational/governance Micro-RAG only; no patient-specific retrieval

## 1. Design goals

The document registry is the source of truth for what Micro-RAG is allowed to retrieve. The index is a disposable derived artifact that can be deleted and rebuilt from the registry. A vector or lexical index must never become the authority for document approval, expiry, revocation, identity mapping or clinical policy.

The design is intentionally edge-compatible: deterministic manifests, content hashes, explicit lifecycle states, atomic rebuild and no mandatory external vector database. An embedding adapter can be added later behind the same interface if measured recall/latency requirements justify it.

## 2. Document lifecycle

```text
DRAFT → APPROVED → DEPRECATED
   └──────────────→ REVOKED

EXPIRED is a retrieval exclusion state, not an approval override.
```

Only `APPROVED`, non-expired, non-PII, non-secret documents with an allowed scope may enter the derived index. `DEPRECATED`, `REVOKED`, expired, unapproved, unowned or PII-containing records are excluded immediately. Re-approval requires a new content hash and an explicit approval event.

## 3. Registry record

Each record contains `doc_id`, title, version, owner, source reference, scope, language(s), lifecycle state, content SHA-256, approval/revocation timestamps, expiry, `contains_pii`, `contains_secret`, and text. The registry stores provenance metadata; the index stores only the minimum chunk text and provenance needed for citation.

Raw HN/AN, names, patient tokens, bearer tokens, private keys, unrestricted clinical notes and full telemetry windows are not accepted into the registry. The scanner is conservative and a failed scan blocks admission rather than attempting to clean content silently.

## 4. Rebuildable index

The index adapter performs deterministic micro-chunking and token indexing from the registry’s eligible records. Each chunk carries `doc_id`, version, `chunk_id`, chunk hash, language and source scope. The index manifest contains the registry manifest hash and index configuration hash. A query result is valid only if the registry manifest hash still matches the index manifest hash.

A rebuild creates a new temporary index, writes the manifest atomically and then swaps it into place. A failed rebuild leaves the previous index unchanged but marks it stale if the registry changed. Revocation/deprecation therefore becomes safe even when a rebuild is interrupted: the query layer must check the registry/index hash and refuse stale results.

## 5. Query contract

Search is scope-filtered and requires a minimum evidence score. It returns provenance-bearing chunks, not free-form answers. It never calls the model, writes to Fixed Hub state, resolves identity or executes commands. The model response adapter remains the next boundary for citation and safety validation.

## 6. Rebuild/delete acceptance evidence

| Test | Required result |
|---|---|
| PII/secret admission | Registry rejects content before indexing |
| Approval gate | DRAFT/unapproved content is absent from results |
| Expiry/deprecation/revocation | Excluded after rebuild |
| Determinism | Same registry and config produce same manifest/index hash |
| Atomic rebuild | Failed temporary rebuild does not corrupt the active index |
| Staleness | Registry/index hash mismatch blocks retrieval |
| Bilingual retrieval | Thai/English approved operational record returns provenance |
| Deletion | Revoked document disappears after rebuild and cannot be cited |
| Scope isolation | Operational query cannot retrieve clinical-governance or untrusted content without explicit scope |

## 7. Future vector adapter

A future FAISS/Qdrant or other semantic adapter must implement the same registry/index interface and preserve the registry manifest hash. It must be evaluated for recall, precision, stale-version exclusion, deletion propagation, rebuild time, encryption, backup/restore and Zero-PII leakage before pilot use. A vector index is a derived cache, not a new authority.
