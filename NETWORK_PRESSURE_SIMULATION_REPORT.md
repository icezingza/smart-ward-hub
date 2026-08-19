# Smart Ward Hub — Network Pressure & Backpressure Simulation Report

**Suite:** `smart-ward-network-pressure-v1`  
**Evidence boundary:** Software simulation only  
**Physical Acer validation:** Pending  
**Production network validation:** Pending

## Executive result

The deterministic offline simulation passed all three scenarios. The bounded queue exposed overload explicitly, partial reads reconstructed valid frames, corruption and PII fixtures were rejected, disconnects were modeled, and duplicate/replay protection remained active. The result demonstrates bounded software behavior under the selected parameters; it does not establish real serial-driver, Wi-Fi, MQTT broker, BLE/RF, switch, power-loss or clinical reliability evidence.

## Scenario results

| Scenario | Devices | Produced | Accepted | Rejected | Queue dropped | CRC rejects | PII rejects | Replay rejects | Disconnects | Max queue | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `serial_burst_saturation` | 8 | 1,024 | 160 | 0 | 836 | 0 | 0 | 0 | 0 | 32/32 | Passed |
| `serial_sustained_partial_reads` | 4 | 320 | 320 | 0 | 0 | 0 | 0 | 0 | 0 | 4/64 | Passed |
| `serial_corruption_reconnect_replay` | 4 | 288 | 231 | 41 | 0 | 16 | 13 | 13 | 20 | 32/32 | Passed |

## Interpretation

The burst scenario intentionally overwhelms a consumer that drains four frames per tick while the producer emits a twelve-fold burst. The simulator dropped 836 frames at the explicit bounded queue boundary and retained a maximum depth of 32, exactly the configured capacity. This is a useful control result, not a clinical data-loss acceptance decision. Whether dropping is acceptable, whether a durable spool is required, and which telemetry class has priority require product and clinical-owner decisions.

The sustained partial-read scenario consumed all 320 produced frames with no queue drop. The corruption/reconnect/replay scenario recorded 16 CRC failures, 13 PII rejections, 13 duplicate/replay rejections and 20 simulated disconnects while maintaining the configured memory bound and replay guard.

## Acceptance checks

| Check | Result |
|---|---|
| Queue never exceeds configured capacity | Passed |
| Codec buffers remain bounded | Passed |
| Saturation is visible rather than silent | Passed |
| Partial reads are reconstructed | Passed |
| CRC mutations do not become packets | Passed |
| PII fixtures are rejected before append | Passed |
| Duplicate/replay sequences are rejected | Passed |
| Disconnect/reconnect reset is modeled | Passed |
| Report contains only synthetic identifiers/counters | Passed |
| Physical/network claims remain pending | Passed |

## Master regression

The pressure regression was added to `run_all_tests.py`. The complete Smart Ward master suite passed after integration, including the new pressure tests, Serial framing tests, P2-002 adapter tests, Micro-RAG tests, Device Trust, workflow, admission, roaming, reliability and 30-day software simulation checks.

## Residual risks and next gates

This result does not measure actual Acer CPU/memory behavior, USB-serial driver buffering, OS scheduler effects, physical cable loss, UART electrical behavior, Wi-Fi contention, MQTT QoS/retained messages, BLE RF loss, gateway CPU limits, power interruption, filesystem durability or real network segmentation. The next gate is to repeat the selected pressure cases on the Acer Spin N17H2 loopback/controlled gateway using `SERIAL_BENCH_VALIDATION_PLAN.md` and record redacted physical evidence.
