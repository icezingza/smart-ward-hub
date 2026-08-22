# P2-002 Transport Selection Readiness Report

**Date:** 22 August 2026
**Status:** `VERIFIED — SOFTWARE-ONLY / FIXTURE-ONLY`
**Decision:** `P2_002_TRANSPORT_SELECTION_VERIFIED`
**Selected first software profile:** Serial
**Physical gate:** `NOT_STARTED`

## 1. Executive summary

The P2-002 transport-selection gate establishes Serial as the first software profile for the Smart Ward Hub adapter workstream. It requires the transport-neutral conformance matrix to pass for MQTT, WebSocket, Serial and BLE before recording the selection. The gate is read-only and does not open a COM port, broker, WebSocket session or BLE device.

The selection is verified only as a **software profile decision**. The physical gate remains `NOT_STARTED`, and hardware evidence remains `UNVERIFIED`. The result does not authorize a serial bench, a clinical device, production network access or any external transport.

## 2. Evidence summary

| Control | Result | Evidence |
|---|---|---|
| Candidate transport allowlist | Passed | MQTT, WebSocket, Serial and BLE are the locked candidate set |
| Cross-transport conformance dependency | Passed | `P2_002_ADAPTER_CONFORMANCE_VERIFIED` |
| Selected software profile | Passed | `selected_software_transport=serial` |
| Physical gate | Not started by design | `physical_gate_status=NOT_STARTED` |
| Hardware evidence | Unverified | No COM/driver/device evidence is asserted by this gate |
| Fixture/read-only boundary | Passed | `fixture_only=true`, `read_only=true`, no transmission or runtime mutation |
| Redaction | Passed | Conformance evidence contains no raw patient/secret markers |
| Authorization | Locked | External authority NONE; production and clinical authorization false |

## 3. Selection contract

The gate requires the existing cross-transport conformance control to return `P2_002_ADAPTER_CONFORMANCE_VERIFIED`, with all four candidates represented, normalized fields complete and the failure matrix complete. Serial is selected as the first software profile because it is the designated first-transport path in the existing P2-002 architecture and bench plan; this gate does not claim that Serial has passed on Acer hardware.

The selection control rejects a conformance blocker, candidate-matrix drift, selection changes, physical-gate promotion, hardware-evidence promotion, execution-boundary mutation, authorization mutation and redaction failure. A future physical PASS must be produced by a separately approved non-production bench evidence contract; it cannot be created by changing this software selection snapshot.

## 4. Focused and phase-end verification

The focused suite contains six cases: verified Serial selection, conformance blocker, selection/physical-gate mutation, candidate-matrix mutation, execution/authorization mutation and redaction mutation. All cases passed. The phase-end gate additionally checks no network/provider/transport/scheduler imports, selected-profile and physical-boundary locks, exporter round-trip, redaction, private-key exclusion, no-self-authorization and `git diff --check`.

The exporter produces `evals/micro_rag/evidence/p2-002-transport-selection-local.json` with `P2_002_TRANSPORT_SELECTION_VERIFIED`, `freeze_binding_required=true`, `physical_gate_status=NOT_STARTED`, `hardware_evidence=UNVERIFIED`, `redaction_verified=true` and `production_ready=false`. The snapshot is a local internal evidence artifact and is not an external submission.

## 5. Residual risks and next evidence

The next physical step, if separately authorized, is a non-production Serial bench on the Acer Spin N17H2 with an explicitly approved COM port and isolated fixture. Required evidence includes driver/port enumeration, framing and partial reads, disconnect/reconnect, queue pressure, Device Trust handoff, power interruption behavior and redacted bench records. The current environment previously recorded no enumerated COM device; this selection gate does not alter that result.

MQTT broker/ACL/TLS, WebSocket long-lived-session behavior, BLE pairing/RF/MTU/reconnect, gateway attestation, hardware signing/key custody, production network segmentation, HIS/IdP/mTLS and clinical validation remain unverified or pending. No candidate transport should be promoted to physical or production use from this software gate alone.

> The supported claim is **Serial selected as the first software profile inside a controlled production prototype**. It is not a claim of production-ready transport, clinical readiness, hardware validation, tamper-proof operation or 100% HIPAA/PDPA compliance.

## 6. Authorization boundary

External Gates remain `7 BLOCKED / 3 OPEN / 0 PASSED`. The gate preserves `external_authority=NONE`, `runtime_authority=NONE`, `clinical_validation_authorized=false`, `production_authorized=false` and `pilot_gate_status=BLOCKED_PENDING_EXTERNAL_AUTHORIZATION`. It performs no external transmission, runtime mutation or authorization promotion.

## 7. Files and verification

| Item | Path / value |
|---|---|
| Selection evaluator | `p2_002_transport_selection.py` |
| Exporter | `export_p2_002_transport_selection.py` |
| Focused tests | `test_p2_002_transport_selection.py` — 6 passed |
| Phase-end gate | `test_p2_002_transport_selection_phase_end_hardening.py` — passed |
| Master integration | `run_all_tests.py` |
| Evidence snapshot | `evals/micro_rag/evidence/p2-002-transport-selection-local.json` |
| Feature commit | `48012d134d0e4838e4b9005829a52f8d4769de5e` |
| Initial freeze source | `48012d134d0e4838e4b9005829a52f8d4769de5e` |

The release-freeze must be refreshed after this report and traceability update. Master regression and final hygiene/alignment remain required before handoff.
