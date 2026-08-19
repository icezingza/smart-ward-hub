---
name: smart-ward-agent-task-router
description: Route Smart Ward Hub engineering and operational tasks by safety risk, capability, dependency and evidence. Use when a request spans security, backup, deployment, hardware, HIS, roaming, or clinical workflow.
---

# Smart Ward task routing

Use the global `agent-task-router` skill, then classify the request before action.

| Class | Route | Approval expectation |
|---|---|---|
| Security/auth/device trust | agent-security-auditor, then registry/control room | Explicit approval for exceptions or credential changes |
| Host/deployment | create-vps or setup-control-room | Explicit approval for network or apply |
| Backup/recovery | agent-backup-manager | Explicit approval for restore or retention deletion |
| Scheduled checks | agent-team-cron-planner | Dry-run and overlap/lock review |
| Status/evidence/incident | agent-control-room | Redacted evidence only |
| Agent/service inventory | agent-registry-manager | Explicit approval for enable/disable/revoke |
| Clinical workflow/human factors | security auditor plus clinical reviewer | Never autonomous clinical decision |
| HIS/Admission integration | setup-control-room plus security auditor | Contract and sandbox integration evidence |

## Safety rules

Do not route raw patient data to a skill. Do not treat a clinical alert, admission state or reset request as an ordinary automation task. The Fixed Edge Hub remains authoritative; skills may inspect, validate and propose but must not create a competing source of truth.

Every route records scope, owner, dependency, risk, approval state, expected evidence and rollback. If evidence is missing, route to `Unverified` review rather than claiming completion.
