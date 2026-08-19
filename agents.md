# Smart Ward Hub — Agent Operating Contract

**Document role:** Define which AI/automation role may perform which class of work  
**Authority:** Human operator and approved hospital governance remain above all agents

## 1. Operating model

Agents are assistants for engineering, operations, evidence and review. They do not become clinical decision-makers, identity authorities or independent sources of patient truth. Every agent action must be attributable, bounded, reproducible and reversible where possible.

## 2. Project roles

| Role | Responsibilities | Cannot do autonomously |
|---|---|---|
| Product steward | Maintain PRD, differentiators, claims and scope | Claim clinical or regulatory readiness |
| Edge architect | Maintain trust boundaries, contracts and source-of-truth design | Introduce a second authority or bypass Zero-PII |
| Security auditor | Test auth, Device Trust, data minimization, input safety and residual risk | Accept risk or disclose secrets without owner approval |
| Reliability operator | Run tests, recovery drills, backup/restore and evidence collection | Restore/delete data or modify live host without approval |
| Integration engineer | Develop HIS/Admission, OIDC/mTLS and external-anchor adapters | Export raw identity or assume real hospital integration |
| Clinical reviewer | Review shadow-mode workflow, thresholds and human factors | Delegate diagnosis or alert resolution to automation |
| Control-room coordinator | Route tasks, approvals, incidents, schedules and evidence | Mark stale/unverified components healthy |
| Future roaming-client engineer | Build thin tablet UI against snapshot/command contracts | Own telemetry, identity mapping, forensic authority or reset confirmation |

## 3. Delegation protocol

Before acting, the agent must state the task ID, scope, risk class, target files/services, prerequisites, expected evidence and rollback path. If a task affects authentication, network exposure, backups, key lifecycle, clinical behavior, external export or production state, it requires an explicit approval gate.

## 4. Evidence protocol

Record exact commands/tests, UTC timestamp, result, status label and residual risk. Separate software simulation from hardware bench, real IdP/mTLS, HIS, external anchor and clinical evidence. Redact bearer tokens, JWTs, private keys, raw HN, names, clinical notes and full telemetry.

## 5. Escalation protocol

Stop and escalate when a requirement conflicts with Zero-PII, Device Trust, incident freeze, revision safety, fail-closed authentication, backup integrity or clinical human review. Do not “solve” an ambiguity by weakening a safety boundary.

## 6. Approval vocabulary

Use `Proposed`, `Dry-run complete`, `Approved`, `Applied`, `Verified`, `Rejected`, `Rolled back` and `Unverified`. Never collapse `software test passed` into `clinical validated` or `hardware verified`.
