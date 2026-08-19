# Smart Ward Hub — Acer Spin N17H2 Serial Bench Validation Plan

**Target:** Acer Spin N17H2 as Fixed Edge Hub  
**Scope:** Serial transport framing, partial reads, reconnect, driver behavior, Device Trust handoff and bounded ingestion  
**Current status:** Software framing harness passed; physical Acer evidence not collected

## 1. Safety and scope boundary

This is a laboratory bench procedure. It must run with no active patients, no production HIS connection, no real patient tokens and no clinical decision-making. Use synthetic device IDs and synthetic telemetry only. Do not connect an unverified sensor to a live ward network. Do not install unsigned drivers or execute vendor binaries that have not been reviewed.

The procedure validates the Acer host, serial transport and adapter boundary. It does not validate clinical accuracy, C60 medical performance, BLE behavior, HIS interoperability, OIDC, mTLS, power-loss tolerance or clinical workflow safety.

## 2. Required bench assets

| Asset | Required state | Evidence to record |
|---|---|---|
| Acer Spin N17H2 | Dedicated lab/maintenance state; no patient session | OS build, hostname, date/time source, power mode |
| USB-serial adapter or approved gateway | Known model and driver; isolated from patient network | Vendor/model, driver version, serial number or redacted asset ID |
| Loopback fixture | TX connected to RX only for first test | Wiring photo or operator attestation |
| Synthetic telemetry fixture | Generates only `TelemetryPacket v1` test frames | Fixture version and corpus hash |
| Fixed Hub software | P2-002 adapter baseline and test suite installed | Git commit/hash, Python/runtime version |
| Optional signature fixture | Synthetic Ed25519 key only; never production key | Key ID and public-key fingerprint only |
| Power source | AC with controlled disconnect procedure | AC/battery state and test operator |

## 3. Preconditions

Before connecting a serial device, verify that the Acer is not running a production ward service and that the test database, telemetry state and audit paths point to a disposable lab directory. Confirm that the selected serial port is not used by another process. Record the port name, baud rate, data bits, parity, stop bits and flow-control settings from the approved fixture contract; do not guess these values from a vendor default.

The first physical test should use a USB-serial loopback fixture, not a sensor attached to a patient or a live gateway. Only after loopback framing passes may a synthetic gateway be connected. The adapter must remain in observe or enforce mode according to the approved test case; disabled mode is suitable only for parser development and cannot produce pilot evidence.

## 4. Validation sequence

| Step | Test | Pass condition | Evidence class |
|---|---|---|---|
| S-001 | Host inventory | Acer model, OS, driver and port are recorded | Physical |
| S-002 | Port exclusivity | No competing process and no unexpected data before test | Physical |
| S-003 | Loopback full frame | Encoded frame returns byte-identically and decodes once | Physical + software |
| S-004 | Partial reads | One-byte and irregular chunks reconstruct exactly one frame | Software baseline; physical repeat required |
| S-005 | Back-to-back frames | Two frames decode separately with sequence 1 then 2 | Physical + software |
| S-006 | Truncation | Incomplete frame emits no telemetry and waits boundedly | Physical + software |
| S-007 | CRC mutation | Corrupt frame is rejected and no packet reaches ingress | Physical + software |
| S-008 | Oversize declaration | Declared oversized payload is rejected before allocation | Physical + software |
| S-009 | Noise/resynchronization | Leading noise cannot create a packet; next valid frame recovers | Physical + software |
| S-010 | Disconnect/reconnect | Partial old frame is discarded or timed out; new frame resumes only with newer sequence | Physical |
| S-011 | Device Trust | Missing/invalid signature fails in enforce mode; valid synthetic signature reaches Fixed Hub verification | Physical + software |
| S-012 | Adapter boundary | No PII, secret or workflow command is forwarded | Physical + software |
| S-013 | Bounded pressure | Queue, memory and error rate stay within approved limits under fixture load | Physical |
| S-014 | Service restart | Restart does not reset local sequence guard or accept replay | Physical + software |
| S-015 | Audit evidence | Accepted/rejected outcomes contain no raw frame, patient token or secret | Physical + software |

## 5. Framing contract

The bench fixture uses the following laboratory wire format:

```text
STX(0x02) | VERSION(0x01) | FLAGS(0x00) | PAYLOAD_LEN(uint16 BE)
| UTF-8 JSON PAYLOAD | CRC32(uint32 BE) | ETX(0x03)
```

CRC32 provides integrity detection only. It is not authentication. Device Trust remains responsible for Ed25519 verification over the canonical normalized packet. A CRC-valid malformed JSON payload must still be rejected by the adapter.

The deterministic software tests are implemented in `serial_framing.py` and `test_serial_framing.py`. They cover full frames, one-byte reads, irregular chunk boundaries, concatenated frames, truncation, CRC errors, bad terminators, oversize declarations, noise, bounded buffer overflow, reset after disconnect and adapter handoff.

## 6. Evidence record

Each physical run should create one redacted record containing:

```json
{
  "run_id": "serial-bench-YYYYMMDD-001",
  "host_model": "Acer Spin N17H2",
  "os_build": "record exact build",
  "hub_commit": "record commit hash",
  "adapter_id": "adapter-serial-bench-001",
  "port": "COMx or /dev/tty…",
  "serial_parameters": {"baudrate": 115200, "bytesize": 8, "parity": "N", "stopbits": 1},
  "fixture_id": "synthetic-fixture-001",
  "tests": {"S-003": "PASS", "S-004": "PASS"},
  "device_trust_mode": "enforce",
  "key_id": "synthetic-key-id-only",
  "public_key_fingerprint": "sha256-only",
  "pii_scan": "PASS",
  "operator": "role or redacted operator ID",
  "notes": "no patient data; no production network"
}
```

Never record raw frames, bearer tokens, private keys, patient identifiers, names, HN/AN or unrestricted clinical text. Store evidence under the approved redacted evidence directory and keep it separate from runtime database and telemetry checkpoints.

## 7. Stop conditions

Stop the bench immediately if the port receives unexplained external traffic, the device presents an unknown driver prompt, a frame contains identity or command fields, the adapter accepts a replay, the host loses time synchronization, the process grows beyond its configured memory bound, or any test would require a real patient/device pairing. A failed safety or trust gate is not a reason to bypass the gate; it is a blocker requiring investigation.

## 8. Readiness decision

Software framing tests passing means **software framing baseline verified**. The Acer host is not bench-validated until S-001 through S-015 have evidence. P2-002 remains **In Progress** until one real transport passes the physical gates. Even after that gate, clinical validation, HIS/IdP integration and power-loss validation remain separate gates.


## 9. Safe runner commands

The cross-platform `serial_bench_runner.py` is dry-run-first. It lists ports without opening them:

```bash
python serial_bench_runner.py --list-ports
```

It runs only the synthetic framing self-check and writes redacted evidence:

```bash
python serial_bench_runner.py --dry-run --output serial_bench_evidence.json
```

The physical path requires both an explicit port and the exact non-production confirmation phrase. It must not be executed until a loopback fixture or controlled gateway is physically connected and the operator has confirmed that no production network or patient device is involved:

```bash
python serial_bench_runner.py \
  --port COMx \
  --baudrate 115200 \
  --confirm-physical I_HAVE_A_NONPRODUCTION_LOOPBACK \
  --output serial_bench_evidence.json
```

The current read-only Acer inventory found Windows 11 Pro build `26200`, Python `3.14.3`, no enumerated `Win32_SerialPort` entries and no Smart Ward Hub workspace at the checked attached Windows path. Therefore the physical command remains blocked until a non-production serial fixture is connected and the project/runner is placed on the Acer.
