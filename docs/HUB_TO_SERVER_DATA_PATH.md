# Hub-to-Server Data Path

## Recommended topology

```text
Smart Watch -> Ward Hub -> Local SQLite/WAL + audit + bounded telemetry buffer
                           |
                           v
                     durable outbox / handover aggregate
                           |
          mTLS + OAuth2/OIDC service identity + idempotency key
                           |
                           v
                 Hospital Integration Server / HIS FHIR gateway
                           |
             structured acknowledgement with matching bundle ID
                           |
                           v
                 Hub retains or purges only the exact accepted aggregate
```

## Data rules

- Send **aggregates, handover bundles, alert lifecycle and approved operational events**, not an uncontrolled raw telemetry firehose.
- Use a stable `bundle_id` and idempotency key for every server delivery attempt.
- Include schema/profile version, UTC timestamps, Hub identity, ward scope and a redacted audit correlation ID.
- Keep raw HN/AN and identity mapping inside the authorized HIS/Admission Gateway boundary.
- The Hub must retain data after timeout, TLS failure, `429`, `5xx`, malformed reply, wrong bundle ID, wrong profile or generic `200` without the required acknowledgement fields.

## Delivery lifecycle

```text
LOCAL_AGGREGATED -> VALIDATED -> OUTBOX_QUEUED -> SENT
  -> ACKNOWLEDGED -> PURGE_ELIGIBLE -> PURGED
  -> RETRY_PENDING -> DEAD_LETTER -> OPERATOR_REVIEW
```

Only a structured `200` acknowledgement with the exact `bundle_id`, acknowledgement ID, receiving system, server time and accepted version/profile may move an item to `PURGE_ELIGIBLE`. Retries must keep the same idempotency key and use a bounded exponential backoff. Authentication/contract failures must not retry forever.

## Hospital-scale simulation

```powershell
python hospital_full_system_simulation.py --wards 5 --beds-per-ward 40 --ticks 8
```

The default profile creates 5 synthetic wards x 40 beds = 200 beds. It pairs every device through FastAPI, injects fall/vital/disconnect/perimeter/BP-capability scenarios in every ward, and checks one aggregate/handover delivery per ward. It first simulates a `503` response and verifies local retention, then a matching structured acknowledgement and verifies the allowed scoped purge.

This is a local contract simulation. It does not open a network connection or prove a real server, mTLS certificate, OIDC identity, hospital FHIR profile, physical Hub capacity, clinical safety, or production readiness.
