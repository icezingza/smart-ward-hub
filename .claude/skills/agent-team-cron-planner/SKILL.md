---
name: smart-ward-agent-team-cron-planner
description: Plan and validate recurring Smart Ward Hub health, backup, audit and evidence-verification jobs without automating clinical decisions. Use when scheduling checks, retries, locks, notifications or multi-agent workflows.
---

# Smart Ward recurring jobs

Use the global `agent-team-cron-planner` skill as the scheduling baseline. Store schedules in UTC internally and display the ward-local timezone for operators.

## Allowed recurring jobs

Health checks, service restart observation, WAL/storage checks, backup verification, audit-log review, forensic-anchor verification, certificate-expiry checks and evidence-report generation are allowed when least privilege, locks, timeout, retry/backoff and idempotency are defined.

## Prohibited automation

Do not schedule automatic clinical triage, alert resolution, alarm suppression, patient admission authorization, RESET_CONFIRM, credential revocation without approval or external export without an allowlisted destination and explicit approval.

## Required job spec

Record `job_id`, owner, schedule, timezone, dependencies, concurrency policy, timeout, retry/backoff, lock, input scope, output/evidence path, notification policy, rollback and approval state. Test dry-run, duplicate execution, missed runs, clock edges and failure injection. Report installed scheduler, next run, last run, exit code, duration and redacted log path; otherwise label the job `Planned` or `Unverified`.
