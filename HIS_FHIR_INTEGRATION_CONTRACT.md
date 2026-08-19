# Smart Ward Hub — HIS/EMR FHIR Integration Contract

**Status:** Draft for HIS integration review  
**Transport:** Production requires mTLS and an approved OAuth2/OIDC service identity.

## Contract purpose

The Edge Hub generates a shift handover digest and a FHIR `Bundle` of `Observation` resources. The Bundle is a proposed integration payload and must be validated against the hospital's accepted FHIR version, profiles, terminology, and patient-reference policy before production use.

The Edge Hub is not allowed to purge local aggregates merely because a request was sent. It may purge only after a verified acknowledgment from the remote system.

## Sync lifecycle

```text
GENERATED → VALIDATED → SENT → ACKNOWLEDGED → PURGE_ELIGIBLE → PURGED
                         └→ RETRY_PENDING → DEAD_LETTER
```

| State | Meaning | Local data behavior |
|---|---|---|
| GENERATED | Bundle created locally | Retain aggregate |
| VALIDATED | Local contract validation passed | Retain aggregate |
| SENT | Request transmitted | Retain aggregate |
| ACKNOWLEDGED | Remote response validated and status 200 | Eligible for purge |
| RETRY_PENDING | Timeout or retryable 5xx | Retain aggregate |
| DEAD_LETTER | Retry policy exhausted | Retain aggregate and alert operator |
| PURGED | Deletion completed after acknowledgment | Retain manifest/audit record |

## Idempotency and acknowledgment

Each Bundle must have a stable `bundle_id` and an idempotency key. A retry with the same idempotency key must not create a duplicate clinical record. A valid acknowledgment must identify the bundle, the receiving system, the response status, the server time, and the accepted version/profile. A generic `200 OK` without a matching body is insufficient for a high-assurance integration.

The local `SyncAttempt` table must retain success and failure attempts. Purge must be scoped to the exact `device_id`, `bundle_id`, and aggregate time window. It must never delete all aggregates for a device merely because one Bundle succeeded.

## Failure policy

Timeouts, connection failures, certificate errors, malformed responses and retryable server failures must retain data. Retry with exponential backoff and a bounded attempt count. Authentication or validation failures must move to a dead-letter state and require operator review rather than infinite retry.

## Required hospital decisions

The HIS team must confirm FHIR version, accepted profiles, terminology service, patient reference strategy, observation status policy, time zone, consent/retention policy, acknowledgment body, error contract, idempotency behavior, certificate authority, token issuer, monitoring endpoint and support contact before integration testing begins.
