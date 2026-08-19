---
name: smart-ward-agent-security-auditor
description: Audit Smart Ward Hub code, APIs, authentication, Zero-PII boundaries, Device Trust, storage and deployment claims with reproducible evidence. Use for security review, release gates, residual-risk updates or production-readiness claims.
---

# Smart Ward security audit

Use the global `agent-security-auditor` skill as the audit baseline. Start with asset inventory, trust boundaries, threat model and evidence register. Review FastAPI routes, auth modes, scopes, OIDC/JWKS, mTLS configuration, rate limiting, SQLite/WAL, migrations, audit redaction, forensic hash chains and Device Trust.

## Finding discipline

Every finding records severity, exact path/line or command, impact, non-destructive reproduction, remediation, owner and residual risk. Classify results as `Implemented`, `Experimental`, `Planned`, `Not Found` or `Unverified`. A functional test is not clinical validation, hardware evidence, external anchoring or compliance certification.

## Mandatory probes

Use safe invalid-auth, missing-auth, malformed JSON, oversized payload, stale revision, duplicate command, rate-limit and path/input probes in an isolated environment. Redact tokens, signatures, private key material and all patient identifiers from output.

## Non-negotiable claims

Never claim `clinical-ready`, `production-ready`, `tamper-proof`, `100% HIPAA compliant` or `100% PDPA compliant` from software tests alone. Use **controlled production prototype**, **functional verification passed**, **pilot-ready foundation**, **clinical validation pending** and **pilot deployment configuration pending**.
