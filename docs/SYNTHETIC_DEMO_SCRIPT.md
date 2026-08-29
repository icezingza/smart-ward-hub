# Smart Ward Hub — Synthetic Demo Script

**Audience:** technical investor, design partner, hospital IT/clinical owner  
**Data rule:** synthetic IDs and synthetic telemetry only; no real patient data.

## Demo objective

Show that Smart Ward Hub provides an authoritative, bounded and auditable ward workflow under normal, degraded and recovery conditions. The demo must not claim diagnosis, clinical effectiveness, regulatory approval or production authorization.

## Scenario

A synthetic ward has three beds and two registered telemetry devices. Device A sends normal samples, then sends a duplicate and an out-of-order sequence. The network is interrupted while an alert is present. The operator acknowledges the alert, the connection returns, the system reconciles state, a handover is prepared, and a simulated HIS acknowledgment completes the allowed workflow. The demo ends with a backup/restore verification and a redacted evidence export.

## Sequence

| Step | Action | What to show | Expected result |
|---:|---|---|---|
| 1 | Start from versioned release | commit, environment fingerprint without secrets | reproducible version |
| 2 | Register synthetic device | device trust/key ID and scope | approved device only |
| 3 | Send valid telemetry | Edge/Hub state and sequence | accepted and bounded |
| 4 | Replay/alter packet | rejection and audit event | duplicate/stale input rejected |
| 5 | Trigger synthetic alert | alert state and operator scope | no diagnosis claim |
| 6 | Disconnect network | degraded status and local buffer | no false trust or unsafe resume |
| 7 | Reconnect | cursor/revision reconciliation | no duplicate command |
| 8 | Prepare handover | opaque reference and audit ID | raw identity remains outside Hub |
| 9 | Send valid simulated acknowledgment | explicit contract result | purge/transition only after valid ACK |
| 10 | Run backup/restore | manifest/checksum and separate target | state can be verified |
| 11 | Export evidence | redacted report and claim boundary | read-only evidence, no authorization promotion |

## Demo acceptance

The presenter must be able to repeat the sequence three times from a clean environment. Each run must record release commit, fixture version, result, duration, error/retry and any manual intervention. A failed run must be shown as a failure and investigated; it must not be hidden by resetting state.

## Investor narrative

Lead with the operational problem and buyer, then show the smallest workflow that is hard to reproduce safely. Explain the trust boundary and why offline/reconnect, idempotency, redaction and auditability matter. Close with what is proven by software, what requires bench/pilot evidence, the first paid use case, and the next measurable milestone.
