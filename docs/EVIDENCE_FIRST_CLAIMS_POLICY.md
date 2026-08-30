# Evidence-First Claims Policy

**Audience:** Product, sales, security, clinical governance, procurement and external reviewers  
**Status:** Mandatory claim vocabulary for repository-derived communications

## Approved language

| Topic | Approved claim | Evidence boundary that must remain visible |
|---|---|---|
| Forensic integrity | **Cryptographically Verifiable Tamper-Evident Audit Trail** | SHA-256 chaining and signature verification can reveal changes covered by the verification scope. This does not prevent privileged modification, key compromise, deletion or loss of locally held evidence. |
| Network and data location | **Hospital-Controlled Data Boundary** | The hospital controls the approved Hub, network routes, identities, destinations and retention policy. A connected ward Hub is not air-gapped. |
| Dispute and incident support | **Traceability & Forensic Readiness** or **ช่วยเพิ่มพยานหลักฐานและกระบวนการพิสูจน์ข้อเท็จจริง** | The system can improve event reconstruction and evidence handling. Legal admissibility and outcome depend on jurisdiction, procedure, custody, independent review and the court. |

## Prohibited affirmative claims

Do not present the system as:

- `Tamper-Proof` or `Tamper-Proof 100%`
- `Air-Gapped` or `Air-Gapped 100%` while any ward, hospital or maintenance network remains connected
- preventing lawsuits, preventing liability or guaranteeing a legal outcome
- automatically court-admissible, legally certified or ISO/IEC 27037 certified without independent evidence

The prohibited terms may appear in engineering documents only when clearly marked as rejected, forbidden, unverified or not supported.

## Evidence-first sentence pattern

Every external claim should state:

1. **Implemented control:** what the software demonstrably does.
2. **Verification evidence:** the test, manifest, signature check or operational record supporting it.
3. **Residual limitation:** what the evidence does not prove.
4. **Promotion gate:** the external, hardware, clinical, legal or operational evidence required before stronger wording is allowed.

Example:

> The Hub provides a Cryptographically Verifiable Tamper-Evident Audit Trail through SHA-256 chaining and optional RSA-PSS signatures. Software regression tests verify change detection within the covered package. External WORM custody, trusted timestamping, production key custody and legal admissibility remain separate validation gates.

## Review ownership

Product owns wording consistency. The technical owner confirms implementation evidence. Hospital IT/security confirms the Hospital-Controlled Data Boundary. Clinical, privacy, legal and regulatory owners approve claims within their authority. A software test cannot self-authorize a clinical, legal, compliance or production claim.
