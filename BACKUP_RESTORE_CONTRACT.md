# Smart Ward Hub — Backup and Restore Contract

**Status:** Software baseline implemented; operational approval and real restore drill pending

## Purpose

This contract defines how the Edge Hub backs up and restores SQLite state without treating a copied database file as sufficient evidence. The backup utility uses SQLite's backup API to take a consistent database snapshot, verifies `PRAGMA integrity_check`, records a manifest with timestamp, source revision, size and SHA-256 checksum, and explicitly excludes secrets and private key material.

The Edge backup boundary covers the SQLite database, optional telemetry checkpoint and optional forensic manifest. Authentication secrets, OIDC private material, mTLS private keys and host credentials are not bundled with the backup. They require a separately governed secret-management and key-custody process.

## Backup lifecycle

```text
PRECHECKED → SNAPSHOT_CREATED → CHECKSUMMED → MANIFESTED → RETAINED
                                  └→ FAILED / NO_PUBLISH
```

| Stage | Required control | Evidence |
|---|---|---|
| Precheck | Source database exists; artifact names are not secret-like; source revision is recorded | command transcript and source metadata |
| Snapshot | SQLite backup API; no raw `.db` copy while WAL is active | backup bundle and SQLite metadata |
| Integrity | `PRAGMA integrity_check` returns `ok` on the snapshot | manifest field |
| Manifest | Schema version, backup ID, timestamp, source revision, file size, SHA-256 and restore status | `manifest.json` |
| Retention | Approved retention window, destination access control and deletion approval | operator record |
| Restore | Separate target, exact non-production confirmation, checksum verification and atomic target replacement | restore transcript |
| Post-restore | Integrity check, schema revision, row-count/hash comparison and service readiness | restore verification report |

## Restore safety

The exact confirmation phrase `I_UNDERSTAND_RESTORE_TO_NONPRODUCTION_TARGET` is required by the utility. Restores are written to a separate target through a temporary file and atomic replacement. A manifest checksum mismatch, path traversal, missing artifact, invalid SQLite state or missing confirmation blocks the restore.

## Strict manifest validation — software baseline

Before restore, the utility now validates the manifest as a closed contract. Unknown or missing top-level fields, backup-ID mismatch, naive/non-ISO timestamps, blank source revision, secret-boundary mutation, unexpected restore/physical-validation status, unknown artifact kinds, duplicate paths, path separators/traversal, manifest self-reference, secret-like filenames, non-canonical database binding, invalid size/hash types, size mismatch, checksum mismatch and missing/invalid SQLite integrity metadata are rejected fail-closed.

The database artifact must be bound to `database.sqlite3`, contain a lowercase 64-character SHA-256 and declare `integrity_check=ok`. Optional checkpoint/forensic artifacts remain hash- and size-bound and are never allowed to carry private keys, credentials or raw frames. This is a stronger local software contract; the manifest itself is still not an independently anchored or WORM-protected artifact.

`test_backup_restore.py` covers successful isolated restore plus strict mutations for unknown fields, missing database, size mismatch, database path substitution, naive timestamp, tampered artifact, missing confirmation and secret-like artifact rejection. The test result is software evidence only.

The current software regression proves successful restore to an isolated temporary target and verifies a durable fixture row. It does not prove restore to an encrypted Acer volume, a production filesystem, a real backup destination, a real service supervisor or a clinically approved recovery point.

## Retention and recovery boundaries

The project must obtain an approved RPO/RTO, retention duration, backup schedule, destination, encryption method, access-control model, restore owner and disposal procedure before pilot. A backup that has not been restored successfully remains `UNVERIFIED`; a software-only restore is not evidence of disaster recovery on the Acer host.

The operational runbook must continue to require verification of active pairing state, alert state, pending sync state, forensic manifest, schema/migration revision, filesystem ownership and health/readiness before telemetry intake resumes. If restored state is stale, the UI must show reconciliation required rather than presenting the ward as green.

## Claim boundary

This contract supports the product claim **Sovereign Edge / Offline-first with recoverable, tamper-evident local evidence workflow** at the software-contract level. It does not justify the claims **backup-ready in production**, **disaster-recovery proven**, **clinical-ready**, **tamper-proof** or **production-ready** until the external restore and host-validation gates are completed.
