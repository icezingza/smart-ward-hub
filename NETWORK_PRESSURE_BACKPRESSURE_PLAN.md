# Smart Ward Hub — Network Pressure & Backpressure Simulation Plan

**Scope:** Serial and future IoT adapter data-plane pressure  
**Execution mode:** Offline deterministic simulation; no production network and no physical serial port  
**Evidence status:** Software simulation only; physical Acer validation pending

## 1. Objective

The simulation verifies that the adapter path remains bounded and evidence-producing when producers generate frames faster than the downstream consumer can normalize, authenticate and append them. It covers burst traffic, sustained partial reads, queue saturation, malformed/corrupt frames, PII rejection, duplicate/replay, disconnect/reconnect and bounded-memory behavior.

The simulation is not a network penetration test, broker benchmark, operating-system stress test or hardware certification. It does not establish real serial-driver, BLE/RF, MQTT broker, Wi-Fi, switch, power-loss or clinical reliability evidence.

## 2. Pressure model

```text
Synthetic producers → SerialFrameCodec → adapter normalization
                    → bounded ingress queue → slow consumer
                    → EdgeTelemetryStore sequence guard
```

Each producer represents a synthetic device. The producer emits framed `TelemetryPacket v1` payloads using configurable burst multipliers and partial-read chunk patterns. The queue has a fixed maximum depth. The consumer drains a bounded number of payloads per tick. When the queue is full, new payloads are explicitly counted as `queue_dropped`; the simulator never grows the queue without bound.

Corruption and safety conditions are injected at deterministic intervals. CRC mutations must be rejected by the framing codec. Malformed JSON and PII-bearing packets must be rejected by the adapter. Duplicate or out-of-order sequences must be rejected by the existing `EdgeTelemetryStore`.

## 3. Scenario matrix

| Scenario | Purpose | Primary signal |
|---|---|---|
| `serial_burst_saturation` | Burst producers exceed slow consumer | Queue drops are explicit; max queue depth never exceeds capacity |
| `serial_sustained_partial_reads` | Normal sustained load with irregular chunks | All valid frames reconstruct and are consumed without loss |
| `serial_corruption_reconnect_replay` | Fault injection under reconnect and replay | CRC, PII, duplicate and malformed outcomes are classified; memory stays bounded |

## 4. Parameters

The simulator accepts device count, ticks, frames per device per tick, burst start/duration/multiplier, queue capacity, consumer rate, max payload, max codec buffer, partial-read pattern, CRC corruption interval, duplicate interval, disconnect interval, malformed interval and PII interval. The default scenarios are intentionally synthetic and reproducible; the seed is not used because no randomness is required for the baseline.

## 5. Pass/fail thresholds

| Control | Pass condition |
|---|---|
| Queue bound | `max_queue_depth <= queue_capacity` |
| Codec memory bound | Every codec buffer remains `<= max_buffer` |
| Backpressure visibility | Saturation scenario reports `queue_dropped > 0` rather than silent loss |
| Partial reads | Valid frame count matches expected valid frame count in sustained scenario |
| CRC safety | Corrupt frames never become decoded frames |
| PII safety | PII fixtures are rejected before queue/telemetry append |
| Replay safety | Duplicate/out-of-order fixtures are rejected by sequence guard |
| Reconnect safety | Codec reset prevents stale partial frame contamination |
| Evidence boundary | Report labels itself `software_simulation_only` |
| Physical claim boundary | Physical and production network validation remain `PENDING` |

A pressure run that drops frames can still pass if the drop is explicit, bounded and visible, provided the selected pilot policy defines whether dropping is acceptable. This baseline does not choose a clinical loss policy; that requires system owner and clinical review.

## 6. Execution

```bash
cd /home/ubuntu/smart-ward-hub
python3 network_pressure_simulation.py --output /tmp/network_pressure_result.json
python3 test_network_pressure_simulation.py
```

The JSON report contains only synthetic device IDs, counters, scenario parameters and redacted failure classes. It must not be populated with patient identifiers, production tokens, raw frames, private keys or live network addresses.

## 7. Physical handoff

After the software simulation passes, repeat only the approved subset on Acer Spin N17H2 using `SERIAL_BENCH_VALIDATION_PLAN.md`: loopback, partial reads, burst pressure, queue overflow, disconnect/reconnect and service restart. Record OS/driver/port/serial parameters, fixture hash, memory/CPU observations, queue counters and redacted audit results. Do not connect the bench to a production ward network until network segmentation, firewall rules, certificate/key custody and rollback procedures are approved.
