# Smart Ward Hub — P2-002 Edge IoT Adapter Readiness Report

**Status:** In Progress — software adapter baseline verified; transport/hardware pilot evidence pending  
**Selected first software profile:** Serial framed JSON  
**Other profiles:** MQTT, WebSocket and BLE skeletons implemented

## Evidence summary

| Control | Software status | External evidence status |
|---|---|---|
| TelemetryPacket v1 translation | Passed | Hardware source-field mapping pending |
| Device Trust canonical signature compatibility | Passed | Actual device/gateway key custody pending |
| Missing/invalid signature envelope | Passed | mTLS/gateway attestation integration pending |
| PII/secret/command rejection | Passed | Production frame corpus pending |
| Unknown fields/schema/range rejection | Passed via Pydantic and adapter tests | Per-device firmware variance pending |
| Duplicate/out-of-order replay | Passed via EdgeTelemetryStore | Reconnect behavior on actual transport pending |
| Frame-size bounds | Passed | Transport-specific production limits pending |
| Scope/identity mismatch | Passed | Gateway identity and network segmentation pending |
| Queue/backpressure architecture | Designed | Load/overflow bench evidence pending |
| Serial first-transport gate | Software gate passed | Acer/sensor/driver bench pending |
| Serial framing/partial-read codec | Passed | Full physical loopback, driver and reconnect evidence pending |
| Network pressure/backpressure simulation | Passed | Acer CPU/memory, driver buffering, physical cable and production network pressure pending |
| MQTT broker/ACL/TLS | Designed only | Unverified |
| BLE pairing/RF/MTU/reconnect | Designed only | Unverified |
| WebSocket long-lived session security | Designed only | Unverified |

## Security conclusion

The adapter is a **translator**, not a trust root. Transport pointers such as MQTT topics, BLE addresses, serial ports, WebSocket origins and MAC addresses cannot establish device trust. The Fixed Hub must continue to enforce active pairing, Device Trust mode, canonical signature verification, timestamp skew and sequence monotonicity.

The Serial software framing baseline now uses a bounded `STX | VERSION | FLAGS | PAYLOAD_LEN | UTF-8 JSON | CRC32 | ETX` envelope. The incremental codec passed one-byte reads, irregular chunks, concatenated frames, truncation, CRC mutation, bad terminator, oversize declaration, noise resynchronization, bounded overflow and reset-after-disconnect tests. CRC32 is integrity detection only; it does not replace Device Trust authentication.

The adapter rejects workflow commands and sensitive identity fields before normalization. A normalized packet is still subject to the existing `/api/v1/telemetry` authorization, pairing and Device Trust path. This preserves the Fixed Hub as the sole authority for patient-session, alert, forensic and admission mutations.

## Pilot gate decision

P2-002 is not closed. The software baseline is suitable for the next bench step, including a deterministic pressure simulation that exposes queue saturation and preserves memory/replay bounds. The system must still select one actual transport and produce evidence for driver/broker/RF behavior, disconnect/reconnect, power interruptions, queue pressure, device identity, key custody and packet mapping. Only after one transport passes can a second profile be considered.

The recommended next gate is Serial bench validation on the Acer Spin N17H2 using a controlled gateway or sensor fixture. BLE should remain deferred until the actual BMAX/C60 capability and signing/attestation model are documented.
