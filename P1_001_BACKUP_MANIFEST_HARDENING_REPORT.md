# P1-001 Backup Manifest Hardening Report

**Decision:** `SOFTWARE_VERIFIED`
**Operational status:** `EXTERNAL_DESTINATION_AND_DR_UNVERIFIED`
**Product status:** `NOT_PRODUCTION_READY`

## Scope

This workstream hardens the local Edge backup/restore contract. It does not configure a backup destination, encrypt an Acer volume, set retention/RPO/RTO, operate a service supervisor, or perform a physical disaster-recovery drill.

## Controls implemented

| Control | Software result | Evidence |
|---|---|---|
| Manifest schema | Unknown/missing top-level fields rejected; schema and status fields are fixed | `backup_restore.py::_read_and_verify_manifest` |
| Source/bundle binding | `backup_id` must match bundle directory; source revision must be non-empty | `backup_restore.py` |
| Time integrity | `created_at_utc` must be ISO-8601 and timezone-aware | `backup_restore.py` |
| Artifact boundary | Only database, telemetry checkpoint and forensic manifest kinds are accepted; duplicate/path-traversal/self-reference/secret-like paths rejected | `backup_restore.py` |
| Database binding | Database must be exactly `database.sqlite3` and declare `integrity_check=ok` | `backup_restore.py` |
| Size/hash | Non-negative integer size and lowercase 64-character SHA-256 are required and checked before restore | `backup_restore.py` |
| Restore boundary | Exact non-production confirmation, temporary target and atomic replacement remain required | `backup_restore.py` |
| Negative regression | Unknown field, missing database, size/path/timestamp mutation, tampered artifact, missing confirmation and secret-like input all fail closed | `test_backup_restore.py` |

## Verification result

`python3 test_backup_restore.py` returned `BACKUP_RESTORE_REGRESSION_TESTS_PASSED`. The test includes a successful isolated temporary restore and verifies the durable fixture row. This is repeatable sandbox software evidence.

## Residual external evidence

The following remain outside this software result and must be supplied by the reliability/host/custody owners before pilot or production claims: encrypted destination and ACL, retention policy and deletion approval, RPO/RTO, off-host custody, Acer filesystem and power-loss recovery, service-supervisor restart, restore rehearsal on the target host, post-restore readiness transcript and independent read-back.

> This report supports **Sovereign Edge / Offline-first with recoverable, tamper-evident local evidence workflow** at the software-contract level. It does not support `production-ready`, `clinical-ready`, `tamper-proof` or `HIPAA/PDPA compliant 100%`.
