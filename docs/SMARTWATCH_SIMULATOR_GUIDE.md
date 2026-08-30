# Smart Watch Simulator Guide

## Purpose and boundary

`smartwatch_simulator.py` is a **synthetic, non-clinical** device simulator. It uses the same `TelemetryPacket v1` contract as a Smart Watch so the team can develop and verify Hub ingestion before hardware is available.

It does not simulate sensor accuracy, BLE radio behaviour, battery life, firmware faults, wearer movement, clinical performance, or regulatory acceptance. It must never receive real patient identifiers or be used for clinical decision-making.

## What it verifies now

- packet schema and bounded vital-sign fields
- monotonically increasing device sequence numbers
- duplicate and out-of-order rejection expectations
- an explicit no-send period and recovery with a continuing sequence
- local HTTP ingress into a paired test device when the Hub is running

## Safe first run

The default is dry-run: it creates no network traffic and prints only synthetic evidence.

```powershell
python smartwatch_simulator.py --scenario normal
python smartwatch_simulator.py --scenario replay
python smartwatch_simulator.py --scenario out_of_order
python smartwatch_simulator.py --scenario offline_reconnect
```

## Local Hub connection

Before sending, start an isolated development Hub, pair a synthetic test device, and use a local token with `telemetry:write`. The simulator requires `--send`, requires a token, and only accepts an `http` loopback destination (`127.0.0.1`, `localhost`, or `::1`). It intentionally cannot send to a network or production host.

```powershell
python smartwatch_simulator.py --scenario normal --send --hub-url http://127.0.0.1:8000 --token <local-development-token>
```

Use a disposable database/audit path and synthetic device IDs only. The Hub will reject an unpaired device; this is expected and confirms that pairing remains a separate safety gate.

## Hardware transition

When a Smart Watch arrives, keep the same sequence, timestamp, unit, identity and trust checks. Complete `docs/SMARTWATCH_HUB_INTAKE_CHECKLIST.md` and the physical bench plan before enabling a real BLE, serial, MQTT, or WebSocket transport.
