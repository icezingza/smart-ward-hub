# Software Simulation Coverage Matrix

## Scope

Run the full local, synthetic-only matrix with:

```powershell
python software_simulation_matrix.py --execute
```

If a local console has a short execution timeout, run each domain separately and retain the resulting JSON output:

```powershell
python software_simulation_matrix.py --execute --domain SIM-001
python software_simulation_matrix.py --execute --domain SIM-002
```

The runner covers the ten software domains below. It invokes existing deterministic test fixtures and returns non-zero if any selected fixture fails. It does not send network traffic, contact hardware, use patient data, or authorize pilot/production use.

| ID | Domain | Software scenarios covered |
|---|---|---|
| SIM-001 | Smart Watch telemetry | 30/40-bed synthetic ward, normal, fall, vital anomaly, replay, out-of-order, disconnect/reconnect, malformed envelope, PII and command rejection |
| SIM-002 | Ingestion pressure | burst, partial frames, CRC corruption, queue bound, PII, replay and reconnect |
| SIM-003 | Identity and trust | auth fail-closed, scope, pairing, signatures and device lifecycle |
| SIM-004 | Ward workflow | session lifecycle, admission, roaming, scoped/idempotent commands |
| SIM-005 | Alerts and shadow mode | stale revision, alert reconciliation, diagnostic-label rejection and review controls |
| SIM-006 | Recovery | WAL, checkpoint corruption, disk-full injection, tamper, backup/restore and reconciliation gate |
| SIM-007 | Forensics | audit-chain tamper detection and anchor failures |
| SIM-008 | HIS/FHIR | opaque identity, acknowledgement mismatch, timeout and retention |
| SIM-009 | Workers | bounded retry, queue backup, replay eligibility and approval gate |
| SIM-010 | Deployment configuration | OIDC/mTLS fail-closed checks, Windows ACL fixture and migration startup |

## Mandatory external gates

The runner intentionally reports these as `EXTERNAL_UNVERIFIED` because software simulation cannot replace them:

- Smart Watch sensor, firmware, BLE/radio range and battery bench
- Hub host, UPS/power-cut, physical storage and tamper bench
- Real OIDC, mTLS, certificate rotation/revocation and network segmentation
- Authorized HIS/FHIR sandbox exchange
- Clinical governance, human-factors review, training and shadow-mode approval
- Privacy/legal review and independent WORM/timestamp custody

An all-green matrix therefore means **software simulation passed**, not clinical, hardware, legal, pilot, or production approval.
