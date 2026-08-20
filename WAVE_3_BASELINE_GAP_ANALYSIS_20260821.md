# Wave 3 Baseline Gap Analysis

**Date:** 2026-08-21

**Scope:** GV-02 Privacy/Security, GV-05 Acer Host Hardening, GV-09 Clinical Operations, GV-01 Clinical Governance

**Decision boundary:** This document is an internal software-readiness analysis. It does not appoint owners, approve clinical work, validate the Acer host, or authorize production/pilot execution.

## 1. Evidence-based baseline

The production-readiness roadmap places Wave 3 after the completed Wave 0 governance preparation, Wave 1 technical foundation and Wave 2 HIS/forensic boundary work.[1] The blocker matrix still classifies GV-01 and GV-05 as unresolved external blockers and GV-09 as a high-severity operational blocker.[2]

| Gate | Software baseline already present | External evidence still missing | Classification |
|---|---|---|---|
| GV-02 | Zero-PII markers, auth/secret boundary tests, redaction and retention contracts exist in the repository | Independent privacy/security review, site/screen review, retention/RBAC decision, incident-response owner and residual-risk acceptance | Software baseline: Implemented; external review: Unverified |
| GV-05 | `p1_002_host_hardening_readiness.py` validates 13 host controls, safe defaults, out-of-tree runtime references, loopback reference and locked execution state | Acer Windows account/ACL, encryption, firewall/ports, time, patch inventory, auto-start/restart, physical power behavior, kiosk/privacy and real restore evidence | Software preparation: Implemented; host validation: Unverified |
| GV-09 | Clinical shadow-mode, manual-fallback references, RESET_PENDING and outside-in workflow contracts are present; software state remains disabled/pending | Staff competency, manual-fallback SOP sign-off, escalation roster, alarm-fatigue review, downtime drill, clinical stop authority and ward walkthrough | Software preparation: Experimental/Implemented by contract; clinical operation: Unverified |
| GV-01 | Clinical validation preflight requires intended use, exclusions, owners, governance, consent/waiver, training, rollback, manual fallback, device/HIS/transport and analysis gates | Approved protocol, named committee/clinical owner, consent/waiver decision, safety thresholds, human-factors review, adverse-event plan and written committee decision | Software preflight: Implemented; governance decision: Unverified |

## 2. Trust-boundary analysis

The principal Wave 3 risk is not the absence of software checks. It is the possibility that a local manifest or simulation result is mistaken for evidence from a hospital host, clinical authority or independent reviewer. The new readiness package should therefore bind every track to an evidence class, an external-required flag, a stop condition and the same locked authorization boundary used by earlier waves.

For GV-02, the package must distinguish tested marker redaction from a complete privacy review. For GV-05, a validator can check the shape of a Windows host evidence record but cannot prove disk encryption, ACLs, firewall state, physical power behavior or a successful restore on Acer. For GV-09 and GV-01, software can enforce that notification, threshold, protocol and workflow changes remain approval-gated, but it cannot replace staff training, human-factors review, clinical committee approval or a real downtime drill.

## 3. Wave 3 design decision

The next implementation should create one strict machine-readable readiness contract with four tracks: `GV-02`, `GV-05`, `GV-09` and `GV-01`. The contract should be blank-safe, reject unknown nested fields, reject raw identity/contact and secret markers, isolate caller mutations, bind software state to exact track definitions, and reject any attempt to set clinical, production, runtime or pilot authorization.

The contract should use the following states:

```text
status= WAVE3_SOFTWARE_PREPARATION_READY
execution_status= NOT_STARTED
clinical_governance= PENDING
host_validation= UNVERIFIED
privacy_review= UNVERIFIED
clinical_operations= NOT_STARTED
external_owner_appointment= PENDING_EXTERNAL_APPOINTMENT
external_authority= NONE
clinical_validation_authorized= false
production_authorized= false
runtime_authority= NONE
pilot_gate_status= BLOCKED_PENDING_EXTERNAL_AUTHORIZATION
```

## 4. Mandatory stop conditions

Stop if a manifest contains raw HN/AN/MRN/National ID, a secret or contact identifier; if a host control is represented as verified solely by a template; if the process binds to a non-loopback address without an approved gateway; if runtime state or backups remain inside the source tree; if a clinical signal is described as diagnosis or treatment instruction; if a staff or downtime drill is implied without a signed record; if a protocol, threshold or notification change bypasses external approval; or if local software output is used to claim clinical-ready or production-ready status.

## References

[1]: `file:///home/ubuntu/smart-ward-hub-reconcile/PRODUCTION_READINESS_ROADMAP_20260820.md` "Production Readiness Roadmap"

[2]: `file:///home/ubuntu/smart-ward-hub-reconcile/CONTROLLED_PILOT_BLOCKER_ANALYSIS.md` "Controlled Pilot Blocker Analysis"

[3]: `file:///home/ubuntu/smart-ward-hub-reconcile/P1_HOST_HARDENING_CHECKLIST.md` "P1 Host Hardening Checklist"

[4]: `file:///home/ubuntu/smart-ward-hub-reconcile/WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md` "Wave 0 Governance Review Checklist"

[5]: `file:///home/ubuntu/smart-ward-hub-reconcile/clinical_validation_readiness.py` "Clinical Validation Readiness Preflight"
