# Smart Ward Hub — Pilot Operations Runbook v0.1

**Status:** Draft; must be adapted to the selected hospital/site and reviewed by IT, security and clinical owners.

## Before deployment

Confirm release commit, approved hardware/firmware, intended-use record, site network diagram, OIDC/mTLS configuration, runtime directories outside source tree, filesystem ownership, firewall rules, backup destination, retention, monitoring destination and named on-call contacts. Do not place real secrets, private keys, patient data or production databases in the repository.

Run the release checks in an isolated environment:

```bash
python -m compileall -q .
python -m pip check
pip-audit -r requirements.txt
python run_all_tests.py
python freeze_integrity_monitor.py
```

Record the output, commit, package hashes, OS/runtime versions and configuration fingerprint with secret values redacted.

## Startup gate

Start only when database migration is current, runtime paths are writable by the service account, available disk is above the approved threshold, audit sink is healthy, backup age is within policy, OIDC/mTLS checks pass, and there are no unresolved critical incidents. Static authentication is not allowed in pilot/production unless a separately approved local test exception is active.

## Normal monitoring

Monitor API health/readiness, request error rate, authentication failures, telemetry acceptance/rejection, sequence conflicts, alert backlog, unresolved incidents, worker/sync backlog, database size/lock errors, disk free space, checkpoint age, backup age, audit age, anchor age, certificate expiry and service restart count. Alert thresholds must be approved before pilot and must not be changed solely to make a result pass.

## Backup and restore

Back up SQLite/database state, telemetry checkpoint, audit records and approved evidence artifacts according to the retention policy. Encrypt backups, restrict access, record checksum and timestamp, and keep at least one copy outside the host. Perform a restore drill in an isolated environment before pilot and at every release milestone. Verify migration state, audit continuity, session/bed state, idempotency evidence and ability to resume safely.

## Incident response

For suspected PII exposure, authentication bypass, audit-integrity failure, unsafe reset/discharge, data loss, device spoofing or unexplained state divergence:

1. Stop affected state-changing commands and preserve the evidence snapshot.
2. Record incident ID, time, release, host, device/session scope and operator.
3. Do not delete, rewrite or “repair” evidence in place.
4. Isolate affected device/service or enter approved degraded mode.
5. Notify the technical owner, security owner and clinical owner.
6. Decide rollback or controlled recovery using the approved runbook.
7. Reconcile database, checkpoint, audit, device and HIS state.
8. Document root cause, containment, corrective action and release impact.

## Upgrade and rollback

Create a backup and verify it before migration. Deploy the new version to a staging or pilot slice, run health/readiness and smoke checks, then expand gradually. If a migration or safety check fails, stop rollout and use the tested rollback/recovery path; do not run destructive manual SQL against an unknown production state.

## Pilot closeout

Export only approved, redacted evidence. Record KPI results, incidents, false-alert review, operator feedback, backup/restore result, HIS reconciliation result, unresolved risks and a clinical/customer go/no-go decision. A successful software test or pilot does not automatically authorize clinical use or production scale.
