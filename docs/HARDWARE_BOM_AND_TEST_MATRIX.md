# Smart Ward Hub — Prototype Hardware BOM and Test Matrix

**Purpose:** Build the smallest non-clinical bench that validates transport, identity, resilience and workflow contracts. This is not a medical-device procurement recommendation.

## Minimum BOM

| Item | Qty | Minimum requirement | Evidence to collect |
|---|---:|---|---|
| Edge gateway | 1 | Linux, 4+ cores, 8 GB RAM, SSD, Ethernet/Wi-Fi, UPS-compatible | OS image, serial, disk/CPU/memory, power-loss result |
| Telemetry sender | 2–3 | Programmable BLE/Wi-Fi/serial sender with stable device identifier | Firmware, protocol, device key ID, packet trace |
| Operator client | 1 | Laptop/tablet with supported browser | Browser/version, operator workflow recording |
| Network switch/AP | 1 | Isolated test SSID/VLAN or wired segment | topology, DHCP/DNS, reconnect trace |
| USB/serial adapter | 1–2 | Supported chipset and cable | port mapping, framing/CRC trace |
| UPS/power switch | 1 | Safe power interruption and recovery | outage duration, restart/recovery evidence |
| Test fixture | 1 | Packet replay, malformed packet, delay and burst generation | deterministic fixture version/hash |
| Label/stand-in IDs | set | Synthetic device and bed IDs only | inventory without patient identifiers |

## Test matrix

| ID | Scenario | Pass condition | Evidence |
|---|---|---|---|
| HW-001 | Device enrollment | Only approved device identity is accepted | credential record + audit |
| HW-002 | Normal telemetry | Valid packet reaches Edge/Hub with expected sequence | packet trace + state snapshot |
| HW-003 | Duplicate/out-of-order | Replayed or stale sequence is rejected | rejection code + audit |
| HW-004 | Malformed/oversized | Input is rejected without unsafe allocation | fixture output + resource snapshot |
| HW-005 | Network loss | System enters explicit degraded state without false trust | outage/reconnect timeline |
| HW-006 | Reconnect | Valid state reconciles without duplicate commands | before/after state + audit |
| HW-007 | Device replacement | Hot-swap creates new session and preserves handover link | session evidence |
| HW-008 | Power interruption | Recovery path is deterministic and no unsafe resume occurs | UPS/power trace + recovery report |
| HW-009 | Disk pressure | Startup/resume gate blocks or degrades safely | threshold report |
| HW-010 | Backup/restore | Separate-target restore verifies checksum and state | manifest + restore log |
| HW-011 | Operator workflow | Acknowledge, handover and discharge remain authorized/scoped | screen capture + API audit |
| HW-012 | Privacy | No raw HN/AN/name appears in logs, packets or artifacts | redaction scan |

## Procurement rule

Do not purchase clinical-use hardware until the intended use, jurisdiction, device responsibility, warranty, firmware lifecycle, cybersecurity support window and site acceptance criteria are approved. Prototype hardware must be labelled **non-clinical test equipment** and kept separate from real patient care.
