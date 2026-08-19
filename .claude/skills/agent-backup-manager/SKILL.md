---
name: smart-ward-agent-backup-manager
description: Design and verify safe Smart Ward Hub backups, WAL-aware snapshots, encrypted evidence retention and restore drills. Use before risky changes, during recovery planning or when validating pilot deployment resilience.
---

# Smart Ward backup and restore

Use the global `agent-backup-manager` skill as the procedure baseline. Treat SQLite WAL files as part of the database state; never copy only the main `.db` while it is active.

## Scope

Back up the Edge Hub database, Alembic revision, approved configuration templates, control-plane manifests and evidence metadata. Do not back up raw patient identity, bearer tokens or private keys into the repository. Secret backups require an approved encrypted secret-management destination and separate custody.

## Required manifest

Every backup records source path, source revision, UTC timestamp, size, checksum, retention, encryption state, destination, RPO/RTO target and restore-test status. Use `Unverified` until an isolated restore has actually succeeded and passed schema, WAL, hash-chain and service checks.

Never delete an older backup before the new backup is complete, checksum-verified and independently restorable. A restore requires explicit approval, a reason, an isolated target, a known-good backup and a post-restore verification transcript.

## Zero-PII boundary

Evidence contains only redacted metadata, fingerprints and counts. Do not expose names, HN, raw encounter values, clinical notes, bearer headers, JWTs or private keys.
