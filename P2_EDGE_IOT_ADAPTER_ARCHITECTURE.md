# Smart Ward Hub — P2-002 Edge IoT Adapter Architecture

**สถานะ:** Architecture and software adapter baseline  
**Product boundary:** Controlled production prototype; pilot deployment configuration pending  
**Clinical status:** Clinical validation pending

## 1. Purpose and non-goals

P2-002 adds transport adapters between external IoT hardware and the existing Fixed Hub telemetry ingress. The adapter layer translates transport-specific frames into the locked `TelemetryPacket v1` contract without changing the clinical data model, bypassing Device Trust, or granting external devices direct access to SQLite, alerts, forensic packages or ward workflow state.

The first objective is not to support every protocol. The safe objective is to prove one transport end to end, with packet translation, identity binding, signature/replay controls, malformed-input handling, disconnect recovery and evidence capture. MQTT, WebSocket, Serial and BLE remain separate profiles behind one transport-neutral interface.

The adapter layer does not diagnose, score clinical risk, suppress alerts, confirm reset, pair patients, discharge sessions or resolve identity. It only performs transport framing, device identity lookup, packet validation, optional signature verification and delivery to the existing authenticated telemetry ingress.

## 2. Trust boundary

```text
[External device / sensor]
        │ transport-specific frame; untrusted until verified
        ▼
[Transport adapter boundary]
        │ parse → size/type/schema checks → device identity lookup
        │ signature/attestation → timestamp/sequence checks
        ▼
[Normalized TelemetryPacket v1]
        │ authenticated adapter-to-hub channel
        ▼
[Fixed Hub ingress]
        │ active pairing + Device Trust mode + scope auth
        ▼
[EdgeTelemetryStore / triage / forensic path]
```

The adapter is a **data-plane translator**, not a trust root. NFC, MAC address, BLE address, MQTT topic, serial port, WebSocket origin, gateway name and cached pairing are pointers or routing metadata only. The cryptographic trust root remains the enrolled device credential or an explicitly approved attested gateway credential.

An adapter process must run with least privilege. It may read transport input and write only to the normalized ingestion boundary. It must not read patient mappings, raw admission identifiers, private keys belonging to other devices, forensic packages or unrestricted clinical notes. An adapter crash must fail closed for new packets and must not mutate Fixed Hub workflow state.

## 3. Normalized adapter contract

Every adapter implements the conceptual contract below:

```python
class EdgeIoTAdapter(Protocol):
    adapter_id: str
    transport: Literal["mqtt", "websocket", "serial", "ble"]

    def decode(self, frame: bytes | str, context: TransportContext) -> AdapterResult:
        """Parse one frame without performing clinical side effects."""

    def health(self) -> AdapterHealth:
        """Return non-PII transport state and last failure class."""
```

`AdapterResult` has one of three outcomes: `NORMALIZED`, `REJECTED` or `RETRYABLE_FAILURE`. A normalized result contains only a validated `TelemetryPacket v1`, device key ID, adapter ID, transport metadata, and a redacted evidence record. It never contains `patient_token`, HN/AN, name, bed assignment or raw credentials.

The normalized packet must preserve the locked fields `schema_version`, `device_id`, `sequence`, `timestamp`, `ppg`, `accel_x`, `accel_y`, `accel_z`, `skin_temp`, `battery_pct`, `heart_rate` and `spo2`. A transport may add framing metadata outside the packet, but it may not rename a clinical field, silently infer a missing vital sign or convert units without an explicit versioned mapping.

## 4. Device Trust and replay contract

Each transport profile must declare its trust mode:

| Mode | Allowed use | Required evidence |
|---|---|---|
| Disabled | Development-only parser tests | No pilot evidence; must be visibly marked disabled |
| Observe | Shadow ingestion and compatibility measurement | Signature outcome recorded as unverified; no trust claim |
| Enforce | Pilot candidate | Active credential, Ed25519 signature or approved gateway attestation, timestamp skew and sequence guard |

The preferred model is device-signed canonical telemetry. If the original sensor cannot sign, a BLE/serial gateway may sign a canonical normalized packet only when its own credential is enrolled, its upstream device binding is explicit and the result is labeled as **gateway-attested**, not sensor-origin-authenticated.

Sequence numbers are monotonic per device and remain enforced by `EdgeTelemetryStore`. Duplicate, out-of-order and replayed packets are rejected. Timestamp skew is enforced by Device Trust; transport reconnect must not reset the sequence guard. A reconnect may resume only from a packet sequence that is strictly newer than the last accepted sequence.

## 5. Transport profiles

| Transport | Primary use | Identity pointer | Trust requirement | Main failure risks | Initial pilot decision |
|---|---|---|---|---|---|
| **MQTT** | Gateway-to-Hub telemetry at ward scale | Topic/device ID | TLS/mTLS plus device/gateway signature; topic ACL is not device trust | Retained messages, duplicate QoS delivery, broker compromise, topic spoofing, reconnect storms | Candidate after broker/PKI test |
| **WebSocket** | Local gateway streaming to Fixed Hub | Authenticated session plus device ID | mTLS or OIDC gateway identity plus per-packet device trust | Long-lived session hijack, origin confusion, backpressure, reconnect replay | Candidate for controlled local gateway |
| **Serial** | Direct Acer-to-sensor or bench gateway | Port mapping plus device ID | Signed packet or gateway attestation; OS device ACL | Port reassignment, framing corruption, partial reads, cable removal, USB spoofing | **Recommended first software bench adapter** |
| **BLE** | Direct BMAX/Acer or BLE gateway ingestion | BLE address/service identifier | BLE address is pointer only; require signed payload or attested gateway | Pairing spoofing, address rotation, RF loss, duplicate notifications, battery/MTU variance | Hardware-dependent; defer until bench evidence |

The recommended first pilot path is a **Serial framed adapter in software bench mode**, because it can be tested deterministically without introducing a network broker or RF variability. This does not claim that the final C60/BLE hardware supports the selected frame or signing model.

## 6. Framing and translation rules

Every adapter must enforce maximum frame size, UTF-8/byte validity, bounded parsing time, explicit schema version and field allowlisting. Unknown fields may be logged as a redacted diagnostic but must not be forwarded to the normalized packet. Numeric values must be range-checked before conversion.

Unit conversion must be explicit and versioned. For example, an accelerometer adapter may declare `source_unit=milli_g` and convert to the system unit only in a named mapping version. A missing `heart_rate`, `spo2` or `skin_temp` value must remain `null` only where the Pydantic contract permits it; the adapter must not invent zero or a clinically plausible default.

The adapter must reject frames containing raw HN/AN, names, `patient_token`, free-form clinical notes, bearer tokens, private keys or command verbs such as `RESET_CONFIRM`, `DISCHARGE`, `PURGE` or `RESOLVE_ALERT`. These are not telemetry fields.

## 7. Reliability and backpressure

Adapters use bounded input queues and explicit overflow behavior. When the queue is full, the adapter records `backpressure_drop` with transport and device identifiers only; it must not silently reorder packets or increase memory without a configured bound. The Fixed Hub ring buffer remains the speed layer and SQLite/forensic paths remain controlled by the existing application.

Reconnect logic uses bounded exponential backoff with jitter, a maximum retry window and a circuit-breaker state. Reconnect does not resubmit acknowledged packets. A transport may request resynchronization, but the Hub accepts only strictly newer sequences and never trusts a remote “last accepted sequence” without local evidence.

## 8. Failure taxonomy and audit evidence

Each rejected frame maps to a stable class: `frame_too_large`, `malformed_encoding`, `invalid_json_or_frame`, `unknown_device`, `unknown_key`, `schema_version_unsupported`, `field_out_of_range`, `unit_mapping_missing`, `signature_missing`, `signature_invalid`, `timestamp_out_of_skew`, `duplicate_sequence`, `out_of_order_sequence`, `pii_field_detected`, `command_field_detected`, `queue_overflow`, `transport_disconnect` or `adapter_internal_error`.

Audit evidence contains adapter ID, transport, device ID, sequence when available, failure class, request/correlation ID and timestamp. It does not contain raw frames, patient tokens, bearer tokens, private key material or unredacted clinical payloads.

## 9. One-transport pilot gate

P2-002 cannot be marked pilot-ready merely because an adapter parses a frame. The selected first transport must pass:

| Gate | Acceptance evidence |
|---|---|
| Contract | Valid frame translates to exact TelemetryPacket v1 without field loss or invention |
| Trust | Enforce mode rejects missing/invalid signature or attestation |
| Replay | Duplicate and out-of-order sequence are rejected across reconnect/restart |
| Safety | PII, secret, command and unknown-field frames are rejected/redacted |
| Reliability | Malformed, oversized, partial and disconnected inputs fail boundedly |
| Backpressure | Queue overflow is explicit and memory remains bounded |
| Recovery | Restart/reconnect does not reset sequence or accept stale frames |
| Observability | Non-PII audit evidence records accepted/rejected outcomes |
| Integration | Existing `/api/v1/telemetry` behavior and master regression remain green |
| Hardware | Bench evidence on Acer/gateway and actual sensor transport is recorded separately |

Passing software gates establishes **adapter software baseline verified**. It does not establish BLE/RF, MQTT broker, serial driver, power-loss, network segmentation, hardware reliability or clinical validation.


## 10. Serial bench framing baseline

The first laboratory Serial profile uses a bounded binary envelope: `STX(0x02) | VERSION(0x01) | FLAGS(0x00) | PAYLOAD_LEN(uint16 BE) | UTF-8 JSON PAYLOAD | CRC32(uint32 BE) | ETX(0x03)`. CRC32 is an integrity check only and never replaces Ed25519 Device Trust. The incremental codec is implemented in `serial_framing.py`; it handles partial reads, concatenated frames, truncation, noise resynchronization, CRC failure, bad terminators, oversize declarations, bounded overflow and reset after disconnect.

Physical acceptance is defined separately in `SERIAL_BENCH_VALIDATION_PLAN.md` for the Acer Spin N17H2. Passing the deterministic codec test is software evidence only. Actual COM/tty driver behavior, loopback wiring, disconnect/reconnect, power state, queue pressure, key custody and sensor/gateway compatibility require a redacted physical bench record.
