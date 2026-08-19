---
name: smart-ward-agent-registry-manager
description: Maintain a redacted registry of Smart Ward Hub agents, services, adapters, devices and trust metadata. Use when adding, updating, suspending, revoking or auditing operational components.
---

# Smart Ward registry management

Use the global `agent-registry-manager` skill as the lifecycle baseline. Register control-plane components and trust metadata, not patient records.

## Registry entries

Each entry should include stable component ID, type, owner, version, capabilities, environment, status, last health evidence, dependencies, permission scope, key ID/fingerprint where relevant and rollback/disable path. Do not record private key material, bearer tokens, raw HN, names or clinical notes.

Device credentials must follow the Device Trust lifecycle: `ACTIVE`, `SUSPENDED`, `REVOKED` or expired. Enrollment, suspension, revocation and rotation require an operator identity, reason, audit event and verification evidence. NFC remains a pointer for lookup and is never a root of trust.

## Status discipline

Use `Implemented`, `Experimental`, `Planned`, `Not Found` or `Unverified`. Do not report a component healthy without a recent successful health check. A registered component is not automatically trusted or authorized.

## Approval boundary

Require explicit approval before enabling, disabling, revoking, rotating, deleting or exposing a service or device credential.
