---
name: smart-ward-agent-control-room
description: Operate a transparent Smart Ward Hub control room for status, approvals, run history, incidents, evidence and rollback. Use when supervising deployment, routing, backups, audits, credentials or scheduled checks.
---

# Smart Ward control room

Use the global `agent-control-room` skill as the control-plane baseline. Keep control-plane state separate from application data and never use the control room as a clinical source of truth.

## Required status view

Show component/service ID, version, last heartbeat, active run, queue, failures, approvals, incidents, evidence links and rollback state. Use only redacted metadata. Do not show patient names, HN, clinical notes, raw telemetry, bearer tokens or private keys.

An agent or service may be called healthy only when a recent successful health check exists. Missing or stale evidence is `Unverified`. Every approval, retry, disable, restore, rotate, revoke or network exposure action records actor, action, target, timestamp, result, reason and correlation ID.

## Safety boundary

The control room may observe, coordinate and record. It must not autonomously suppress or resolve patient-safety alerts, authorize admission, confirm destructive reset, reinterpret clinical signals or override Fixed Hub authority.

## Outputs

Produce a redacted status snapshot, run transcript, incident timeline, pending approvals, evidence links and exact next commands. Separate software simulation evidence from real Acer/BMAX hardware and hospital integration evidence.
