# Smart Ward Hub — Memory Contract

**Document role:** Define what the AI workflow should remember, where it belongs and what must never be retained

## 1. Durable project memory

Remember stable decisions, contracts, invariants, evidence status and approved product language. Prefer links to source files over copying long implementation details.

| Memory class | Store | Canonical location |
|---|---|---|
| Product intent | differentiators, target operators, non-goals, claim boundaries | `prd.md`, `PRODUCT_DIFFERENTIATORS.md` |
| Architecture | trust boundaries, authority, data flow, failure behavior | `architecture.md`, `EDGE_HUB_ARCHITECTURE.md` |
| Clinical safety | state machines, stop conditions, shadow-mode rules | `WARD_WORKFLOW_CONTRACT.md`, `CLINICAL_SAFETY_SHADOW_MODE.md` |
| Security | auth modes, scopes, Device Trust, redaction and residual risks | `SECURITY_BASELINE.md`, `RISK_REGISTER.md` |
| Operations | runbooks, backups, recovery and pilot gates | `OPERATIONS_RUNBOOK.md`, `NEXT_PHASE_PRIORITY_MATRIX.md` |
| Agent governance | roles, permissions, workflows and skills | `agents.md`, `rules.md`, `skills.md`, `.agents/` |
| Task state | IDs, priority, dependencies, acceptance evidence and owner | `tasks.md` |

## 2. Working memory

Working memory may contain the current task, selected files, command output summary, active revision/cursor, test result and next action. Keep it ephemeral and redact secrets, patient identifiers and raw telemetry before recording it.

## 3. Prohibited memory

Never retain raw HN, patient name, national ID, address, phone, free-text clinical notes, encounter identity mapping, bearer tokens, JWTs, private keys, TLS private keys, unredacted audit events or raw high-resolution telemetry in AI project memory, prompts, skills, evidence or Git commits.

## 4. Memory quality rules

Every remembered fact must have a source file, commit or test reference where possible. Mark claims as `Implemented`, `Experimental`, `Planned`, `Not Found` or `Unverified`. Add a date when a value can change, such as dependency versions, risk status, hardware state or integration readiness.

## 5. Conflict resolution

When documents disagree, prefer in order: approved runtime contract/tests, current security policy, current architecture, product requirements, roadmap notes, then conversational suggestions. Do not silently reconcile contradictions; record the conflict and ask for an explicit decision when it affects safety or authority.

## 6. Forgetting and retention

Delete transient scratch output after extracting its durable conclusion. Keep runtime databases, checkpoints, audit logs and forensic packages outside Git and outside AI memory unless a redacted fixture is explicitly required for a test.
