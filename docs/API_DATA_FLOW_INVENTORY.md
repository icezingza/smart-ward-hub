# Smart Ward Hub — API and Data-Flow Inventory

**Status:** Engineering draft; validate against the selected pilot topology before external use.

## Logical components

| Component | Responsibility | Trust level | Primary data |
|---|---|---|---|
| Device/adapter | Collect and frame telemetry | Untrusted | Synthetic/device telemetry, sequence, device ID |
| Edge runtime | Validate, buffer and checkpoint telemetry | Protected edge | bounded telemetry, device state |
| Hub API | Authoritative ward/session workflow | Protected core | opaque patient/encounter token, bed/session state |
| Operator/Admission Console | Human workflow interface | Managed client | redacted snapshot, scoped commands |
| HIS/Admission Gateway | Authorized identity/integration boundary | External boundary | raw identity only at approved gateway, opaque references to Hub |
| Evidence/anchor store | Read-only verification artifacts | Controlled evidence | hashes, receipts, audit references |
| Worker/control plane | Durable background work/recovery | Protected service | jobs, leases, retries, audit references |

## API inventory

| Surface | Purpose | Auth/authorization | Mutation boundary |
|---|---|---|---|
| `/health` | Liveness/readiness snapshot | Local/operational policy | Read-only |
| Telemetry ingress | Device samples | Device trust + scope policy | Bounded telemetry state |
| Pairing/device trust | Enroll or verify device | Scoped operator/device identity | Device credential/session |
| Triage/alerts | Generate and acknowledge alerts | User scope + current revision | Alert state/audit |
| Admission preparation | Reserve bed using opaque reference | Gateway/operator scope | Bed/session reservation |
| Admission handoff | Commit prepared admission | Idempotency + scope | Authoritative bed/session state |
| Handover/FHIR | Sync handover and explicit acknowledgement | Gateway scope + contract | Purge only after valid ACK |
| Roaming snapshot/commands | Tablet synchronization | Managed identity + revision | Limited command set |
| Worker control | Recovery/requeue | Separation of duties | Durable job/audit state |
| Evidence/export | Produce redacted evidence | Read-only boundary | No authorization promotion |

## Data-flow rules

Raw HN/AN and direct patient identity must remain inside the authorized Admission Gateway boundary. Hub Core receives only opaque, scoped references. Logs, checkpoints, audit events, evidence exports and telemetry fixtures must pass the redaction scan. Every state-changing command must include authenticated actor, scope, idempotency/revision controls and an auditable result.

The initial pilot must keep the Admission Console loopback-only or place it behind an authenticated gateway in a segmented network. Roaming clients must not call HIS directly. External evidence must remain a receipt/verification boundary until an independently administered service and formal authorization exist.

## Required contract evidence

For each surface, record request/response schema, authentication scope, idempotency key, revision/freshness rule, error codes, audit event, data classification, retention, rollback behavior and test reference. Do not treat OpenAPI reachability or a successful simulated response as proof of clinical safety or production authorization.
