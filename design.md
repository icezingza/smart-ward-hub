# Smart Ward Hub — Design Contract

**Document role:** Interaction, deployment and safety design for AI-assisted implementation  
**Status:** Software baseline documented; real hardware, network and clinical human-factors validation pending

## 1. Design principle

Design Smart Ward Hub as a **visible, state-aware, fail-safe ward operating layer** rather than a generic dashboard. The interface must make authority, freshness, trust, offline state, incident freeze and operator responsibility obvious.

> Fast interaction must never be allowed to become silent destructive action.

## 2. Physical and screen roles

| Surface | Primary role | Authority |
|---|---|---|
| Acer Spin N17H2 Fixed Hub | Ward-local authoritative Edge Hub and nurse-station/controlled admission console | Owns telemetry, pairing, sessions, alerts, evidence, Device Trust and destructive transitions |
| BMAX i11_s candidate | Future managed roaming view/command client for walk-rounds | Reads non-PII snapshot and submits approved idempotent commands; does not own truth |
| HIS/Admission Gateway | Controlled identity boundary | Converts raw HN/AN into opaque token before Hub Core; owns identity mapping |
| External evidence service | Independent anchor boundary | Receives minimized digest/signature/timestamp only after contract and approval |

## 3. Interaction hierarchy

### Fixed Hub

The Fixed Hub shall show ward/bed context, device/session state, freshness, alert severity and operational health. Pairing requires deliberate bed selection and authenticated operator action. NFC may accelerate lookup but cannot prove trust. An active session must move to `RESET_PENDING` and require explicit visual confirmation before close.

### Outside-in Admission Console

The outward-facing console shall display only non-PII bed availability, reservation/task status and freshness. Admission preparation is authenticated, idempotent and tokenized upstream. The console must never become a public patient search, raw HN store or independent database.

### Future Roaming Tablet

The tablet shall display `ONLINE`, `OFFLINE — LAST KNOWN STATE`, stale age, revision/cursor, trust indicators, alert acknowledgement state and admission tasks. Mutating commands use an idempotency key and expected revision. Stale revision returns a conflict and does not mutate Fixed Hub state. Destructive reset confirmation is disabled in the initial pilot.

## 4. Safety-visible states

| State | Required visual meaning | Allowed action |
|---|---|---|
| Fresh/online | Current snapshot has recent Hub heartbeat | Normal approved observation/acknowledgement |
| Stale | Snapshot age exceeds configured freshness window | Reconcile with Fixed Hub; do not assume current bed/alert truth |
| Offline | No live Hub acknowledgement | View last-known non-PII state only; queue/reject according to command policy |
| Trust degraded | Device/network/credential evidence is reduced | Show warning/quarantine path; do not silently stop monitoring |
| Incident frozen | High-resolution evidence is protected | Block unsafe reset/discharge until authorized workflow completes |
| Reset pending | Intentional transition requires confirmation | Confirm on Fixed Hub; keep tablet destructive action disabled |

## 5. Accessibility and operator ergonomics

Use large touch targets, high contrast, short labels, visible severity colors with text equivalents, clear error recovery, no hidden gesture for destructive action, and a persistent clock/freshness indicator. Avoid requiring a nurse to remember an internal cursor or revision; display a human-readable conflict message and the next safe action.

## 6. Design non-goals

Do not optimize for decorative dashboards, autonomous diagnosis, patient identity search on Edge, direct tablet-to-HIS access, silent background purge, or a second mobile database. Do not use generated mockups as evidence of usability or clinical readiness.

## 7. Validation gates

Before the BMAX client is implemented, validate the identity model, OIDC/mTLS, ward Wi-Fi roaming, encrypted mobile cache policy, conflict/reconnect behavior and clinical walk-round workflow. Human-factors review must include alarm fatigue, RESET_PENDING, hot-swap, discharge, admission preparation and offline/stale interpretation.
