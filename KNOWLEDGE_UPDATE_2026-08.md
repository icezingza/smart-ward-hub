# Smart Ward Hub — Knowledge Update

**Update date:** 19 August 2026  
**Source context:** Authenticated Google Notebook, *NamoNexus Enterprise: Sovereign AI for Mental Health Crisis Triage*  
**Status:** Research-informed engineering guidance; not clinical, legal, or regulatory certification.

## Executive update

The Notebook contains 160 sources and emphasizes evidence integrity, standalone operation, cryptographic hashing, hash chaining, digital signatures, forensic evidence formats, and security tooling. The Notebook also warns that generated answers may be inaccurate and should be checked against the original sources. This update therefore separates **verified source findings** from **unverified Notebook claims**.

The most important architectural update is that the current SQLite SHA-256 chain should be treated as a **local tamper-evident mechanism**. It should not be described as tamper-proof or as a legal evidence system. For long-term preservation, the project should adopt an evidence-record approach that includes archive timestamps, verification material, renewal procedures, and external trust anchors. RFC 4998 describes these concepts for long-term proof of existence and integrity.[1]

## Verified findings and engineering implications

| Finding | Evidence status | Impact on Smart Ward Hub |
|---|---|---|
| Evidence records can preserve proof of existence and integrity over long periods | Verified in RFC 4998 | Add an evidence-record export/renewal design above the local hash chain |
| Archive timestamps and timestamp renewal matter when algorithms or certificates weaken | Verified in RFC 4998 | Plan trusted timestamping and key/certificate lifecycle management |
| Merkle/hash-tree structures can represent groups of archived objects efficiently | Verified in RFC 4998 | Consider a batch anchor for forensic packages and handover bundles |
| AFF4 is an open digital-evidence container with hashed image verification and RDF metadata | Verified in pyaff4 documentation | Consider AFF4 as an export/interchange format, not as the live telemetry database |
| The pyaff4 implementation states that some write and signed-statement features are incomplete | Verified in pyaff4 documentation | Do not make AFF4 a production dependency without capability and interoperability tests |
| The selected IoT survey discusses interoperability, data management, analytics, privacy, and edge architecture | Verified at the source URL | Supports interface/versioning and privacy work, but does not validate clinical thresholds or KPI claims |
| Several Notebook links were blocked by anti-bot/security-verification pages | Observed but not source-verified | Do not use those pages as evidence until the documents are directly reviewed |

## Changes to project knowledge

The project documentation should use the following terminology. The local SQLite chain is **tamper-evident** because it can reveal inconsistencies when an attacker changes a payload without recalculating all dependent evidence. It is not tamper-proof because an administrator with database and key access may alter multiple records, delete the database, or replace the local chain. Stronger assurance requires external anchoring, protected key custody, trusted timestamps, immutable retention, and an auditable chain of custody.

The project should distinguish three layers of evidence. The first layer is the live Edge buffer and SQLite operational data. The second layer is the frozen forensic package with canonical payload and local hash linkage. The third layer is an external evidence record containing the package digest, signature, timestamp token, verification policy, and retention metadata. Only the third layer should be considered for long-term preservation workflows.

AFF4 and E01 should not be treated as interchangeable. AFF4 is a container and metadata-oriented evidence format suitable for multiple streams and logical/physical evidence workflows. E01 is commonly associated with forensic disk imaging. The Smart Ward Hub should continue to use SQLite/WAL for operational Edge data and should produce an evidence export only when a forensic package is closed, rather than storing every live telemetry packet as a disk image.

## Required next engineering backlog

| Priority | Work item | Acceptance evidence |
|---|---|---|
| P1 | Add an evidence-export manifest containing package IDs, payload hashes, algorithm identifiers, timestamps, signer identity, and verification policy | Manifest schema test and round-trip verification test |
| P1 | Add external anchor interface with retry, idempotency key, and acknowledgment retention | Mock anchor success/failure/retry tests |
| P1 | Add key custody abstraction so private keys are not stored beside SQLite | Key-provider interface and negative test for missing key |
| P1 | Add trusted timestamp field and renewal metadata | Timestamp validation and renewal-state tests |
| P2 | Add optional Merkle batch anchoring for multiple forensic packages | Proof generation and proof verification tests |
| P2 | Evaluate AFF4 export only after interoperability review | Export/import test with a supported reader |
| P2 | Add chain-of-custody event records: created, sealed, exported, acknowledged, reviewed, retained, disposed | Role-based audit-log test |

## Claims that remain unverified

The Notebook summary does not establish clinical accuracy for fall detection or triage, does not validate the Golden Ratio weighting, and does not prove a 30-bed hardware throughput, battery-life, chemical-durability, or push-notification latency target. Those claims require controlled clinical, hardware, network, and security tests with documented methods and independent review.

## References

[1]: https://datatracker.ietf.org/doc/html/rfc4998 "IETF RFC 4998 — Evidence Record Syntax"

[2]: https://github.com/aff4/pyaff4/blob/master/README.md "aff4/pyaff4 README — Advanced Forensics File Format"

[3]: https://www.mdpi.com/1424-8220/23/19/8015 "MDPI Sensors 23(19) 8015 — IoT survey"
