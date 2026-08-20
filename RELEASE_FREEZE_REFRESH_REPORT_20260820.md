# Release Freeze Refresh Report

**Refresh status:** `PASS`
**Current source revision:** recorded in the machine-readable freeze manifest at publication time
**Freeze manifest:** `evals/micro_rag/evidence/release-candidate-freeze-20260820.json`
**Execution class:** repository/software evidence only

## Decision

The release-candidate freeze is regenerated after each source/documentation change. The machine-readable manifest is the authoritative record of `source_revision`, `origin_main_revision`, file count and publication timestamp. The latest refresh reports `freeze_status=PASS`, `head_matches_origin_main=true`, `working_tree_clean_before_manifest=true`, `secret_marker_scan_pass=true`, `runtime_artifact_scan_pass=true` and `tracked_file_hashes_generated=true`; it covers 318 tracked files and excludes its own hash by design.

The earlier freeze references in historical Wave 0/Wave 1 reports remain historical evidence for their respective source revisions. They must not be read as the current release candidate. The handoff and task documents now point to this refreshed freeze boundary.

## Included controls

The current manifest includes SHA-256 entries for the Wave 1 preparation validator, exporter, regression, identity transport template, preparation package, schema/template evidence, release-freeze regression and master runner. `test_release_freeze_candidate.py` verifies the locked authorization boundary, valid/forbidden claim sets, 7-blocked/3-open/0-passed gate snapshot, current source/origin alignment and selected file hashes.

## Claim and authorization boundary

> This freeze is not production authorization, clinical validation, hardware validation, external custody evidence or a tamper-proof claim.

The manifest preserves:

```text
external_authority=NONE
clinical_validation_authorized=false
production_authorized=false
runtime_authority=NONE
pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
```

The only valid local claims remain **controlled production prototype**, **P0-hardened software baseline**, **functional verification passed**, **pilot-ready foundation** and **clinical validation pending**. Local freeze does not close GV-04, GV-06, GV-08, clinical, HIS, forensic, host-hardening or independent-review gates.

## Next use

External coordinators may use the refreshed source revision and manifest hash as the candidate baseline only after Wave 0 owner appointment, signed scope, approved test window, stop authority, rollback owner, custody owner and independent verification are present. Any source change requires a new freeze; any blocked gate requires explicit reopen before new external evidence is submitted.
