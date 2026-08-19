# Smart Ward Hub — P0 Hardening Report

**Date:** 19 August 2026  
**Decision:** P0 software controls implemented or ready to configure; external identity, certificate, hardware, and HIS validation remain open.

## Implemented changes

| Control | Status | Evidence |
|---|---|---|
| OIDC mode with issuer, audience, JWKS and required claims | Ready-to-configure | `oidc.py`, `security.py` |
| Missing OIDC configuration fails closed | Passed | `test_p0_hardening.py` |
| mTLS launcher requiring server cert, key, and client CA | Ready-to-configure | `run_mtls.sh` |
| Alembic migration baseline | Passed | `alembic/`, `test_p0_hardening.py` |
| Pilot startup requires external migration and disables demo seed | Passed | P0 startup probe |
| SQLite busy timeout and configurable synchronous durability | Implemented | `config.py`, `database.py` |
| Active-only pairing partial indexes | Passed | `models.py`, initial migration, pairing regression |
| Security headers, request ID, TrustedHost | Passed | `main.py`, `test_security.py`, `validate_reliability.py` |
| Zero-PII and TelemetryPacket v1 | Passed previously and in regression | `test_security.py`, `test_edge_runtime.py` |

## Acceptance evidence

The final master suite completed with:

```text
ALL FUNCTIONAL LEVEL 1–6 CHECKS PASSED
```

The suite includes Level 1–6 functional tests, security baseline, fail-closed auth, Edge buffer and recovery, P0 migration/OIDC checks, 30-device concurrent reliability validation, and the 30-day software simulation.

The reliability harness accepted 600 ordered packets across 30 concurrent device streams. The latest measured run recorded approximately 5,557.92 ms wall time for the full 600-request workload. The result is a sandbox software measurement, not a hardware or hospital-network guarantee.

## Deployment modes

The default development mode may use static bearer tokens and startup schema creation. Pilot/production mode should set `SW_ENVIRONMENT=pilot`, `SW_AUTO_CREATE_DB=false`, `SW_SEED_DATA=false`, `SW_AUTH_MODE=oidc`, and run `alembic upgrade head` before starting the API. The mTLS launcher requires `SW_MTLS_CERTFILE`, `SW_MTLS_KEYFILE`, and `SW_MTLS_CA_CERTS` and starts Uvicorn with client certificate verification enabled.

## Residual risk

OIDC JWT validation has not been tested against the hospital's actual issuer, JWKS rotation, audience policy, revocation behavior, or network. mTLS has not been tested with real hospital certificates and CA policy. Alembic has been validated on a clean SQLite database but has not yet been rehearsed against a live pilot database with backup and rollback. External forensic anchoring, key custody, rate limiting, host hardening, power-loss testing, hardware validation, HIS integration, and clinical validation remain open.

The correct status is **P0-hardened software baseline, pilot deployment configuration pending**. It is not a regulatory certification or clinical production approval.
