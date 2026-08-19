# Smart Ward Control-Plane Evidence

This directory is reserved for **redacted coordination evidence**. It must not become a second application database and must not contain raw patient identity, HN, names, national identifiers, clinical notes, bearer tokens, JWTs, private keys or full telemetry payloads.

## Evidence record

Each record should state the check ID, UTC timestamp, actor or skill, target component, command or test reference, result, status label, redaction note, artifact checksum and residual risk. Use stable non-PII identifiers such as service ID, ward code, device key ID or public-key fingerprint where necessary.

## Status vocabulary

Use only `Implemented`, `Experimental`, `Planned`, `Not Found` and `Unverified`. A functional software test does not prove hardware behavior, hospital integration, clinical validity, external forensic anchoring or regulatory compliance.

## Required separation

Keep simulation evidence separate from real Acer Spin N17H2 bench evidence, BMAX device evidence, IdP/OIDC evidence, mTLS evidence, HIS/Admission Gateway evidence and clinical review evidence.

## Retention and handling

Evidence retention, encryption, access control and export destination require an approved policy. Before external export, verify minimization, redaction, destination allowlist and an audit event. Do not place runtime JSON, JSONL, databases or local forensic anchors here unless a reviewed, redacted fixture is explicitly intended.

## Approved project language

Use **controlled production prototype**, **functional verification passed**, **pilot-ready foundation**, **clinical validation pending**, **P0-hardened software baseline** and **pilot deployment configuration pending**. Do not use `clinical-ready`, `production-ready`, `tamper-proof` or `100% compliant` as evidence conclusions.
