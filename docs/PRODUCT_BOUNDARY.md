# Smart Ward Hub — Product Boundary Record

**Status:** Draft for founder, clinical owner, IT/security owner and regulatory review
**Version:** 0.1

## Proposed intended use

Smart Ward Hub is software for **safety-oriented ward monitoring and workflow coordination**. It receives bounded telemetry and opaque patient/encounter references, maintains an offline-capable ward-edge state, presents alerts and operational snapshots to authorized staff, and coordinates handover, admission-preparation and recovery workflows.

The system is intended to support trained hospital personnel. It does not independently diagnose, prescribe, select treatment, or replace clinical judgment. Any clinical claim, alert threshold, or patient-facing use requires separate clinical governance and validation.

## Pilot scope

| Field | Pilot decision |
|---|---|
| Target market | `[DECISION REQUIRED: country/jurisdiction]` |
| First customer type | `[DECISION REQUIRED: hospital/ward type]` |
| First ward | `[DECISION REQUIRED: named ward and site]` |
| Primary users | Ward operator/nurse, ward supervisor, hospital IT/security |
| Clinical owner | `[DECISION REQUIRED: named accountable clinician]` |
| Technical owner | `[DECISION REQUIRED: named service owner]` |
| Supported devices | `[DECISION REQUIRED: approved hardware/firmware matrix]` |
| Integration | HIS/Admission Gateway sandbox first; no direct production write until approved |
| Data mode | Opaque tokens at Edge; no raw HN/AN in Hub Core |
| Pilot duration | `[DECISION REQUIRED: dates and review cadence]` |

## Explicit exclusions

The pilot must not be described as autonomous diagnosis, clinical decision replacement, emergency response certification, production authorization, or compliance certification. The pilot must not use real patient data until the data controller, privacy/security controls, consent/legal basis and clinical governance have approved the protocol.

## Safety boundaries

The service must fail closed for authentication, authorization, invalid telemetry, replayed sequence, stale revision, unsafe reset, unresolved incident freeze, missing migration evidence, audit-integrity failure and unverified external authorization. Degraded connectivity may reduce availability, but it must not silently convert stale or unauthenticated data into trusted evidence.

## Claims policy

| Claim class | Allowed now | Evidence required before promotion |
|---|---|---|
| Software contract | Yes | Automated unit/integration/regression tests |
| Controlled pilot foundation | Yes | Pilot protocol, trained users, site approval and operational gates |
| Clinical effectiveness | No | Clinical protocol, study evidence and clinical sign-off |
| Production-ready | No | Validated release, QMS, security, operations, integration and regulatory decision |
| Tamper-proof/external immutability | No | Independently administered anchor, custody, timestamp and verification evidence |

## Approval record

| Role | Name | Decision | Date | Signature/evidence |
|---|---|---|---|---|
| Product owner |  |  |  |  |
| Clinical owner |  |  |  |  |
| IT/security owner |  |  |  |  |
| Regulatory/quality advisor |  |  |  |  |
| Customer/site owner |  |  |  |  |
