## Smart Ward Hub Change Review

### Change summary

- [ ] This change has a clear purpose and does not expand clinical claims.
- [ ] Product, security and operational impact are described.
- [ ] Branding changes are isolated from API, security, audit and evidence identifiers.

### Safety and privacy

- [ ] No raw patient identifiers, credentials, private keys or production data are included.
- [ ] Authentication, authorization, scope, freshness, idempotency and redaction behavior are reviewed.
- [ ] Any changed state transition has a rollback/stop condition.
- [ ] Clinical/regulatory claims remain explicitly pending unless separately approved.

### Engineering evidence

- [ ] `scripts/verify_local.sh` passes from a clean checkout.
- [ ] `python -m compileall -q .` passes.
- [ ] `python -m pip check` passes.
- [ ] `pip-audit -r requirements.txt` passes or has an approved time-bounded exception.
- [ ] `git diff --check` passes.
- [ ] `run_all_tests.py` passes.
- [ ] Freeze/evidence manifests are regenerated only after source and docs are final.
- [ ] Generated runtime artifacts are absent from the commit.

### Pilot and operations

- [ ] Product boundary and intended use are updated if scope changed.
- [ ] Threat model and risk register are updated for new trust boundaries or hazards.
- [ ] Backup/restore, monitoring, incident and rollback impact is documented.
- [ ] Hardware/HIS/identity assumptions are listed as pending external evidence when not tested.

### Reviewer decision

- **Risk level:** `[low / medium / high]`
- **Required follow-ups:**
- **Approvers:** `[engineering] [security/IT] [clinical/product where applicable]`
- **Decision:** `[approve / changes requested / blocked]`
