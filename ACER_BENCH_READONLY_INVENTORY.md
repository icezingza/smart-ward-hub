# Acer Spin N17H2 — Read-only Bench Inventory

**Inventory mode:** Read-only; no serial port opened; no bytes transmitted; no driver or project files changed.

| Item | Observed result | Evidence status |
|---|---|---|
| Operating system | Microsoft Windows 11 Pro, version `10.0.26200`, build `26200` | Observed on connected Windows desktop |
| Python | `C:\Python314\python.exe`, Python `3.14.3` | Observed |
| Win32 serial inventory | No `Win32_SerialPort` entries returned | No COM device currently enumerated |
| Original mounted workspace | `Namo-IPD-System-V0.1` exists | Observed |
| `smart-ward-hub` sibling workspace | Not found at the checked attached path | Smart Ward Hub code remains in sandbox workspace |
| `AGENTS.md` in checked attached project | Not found | No additional remote instruction discovered |

## Decision

The Acer environment is suitable for a later read-only runner deployment because Windows and Python are present, but the physical Serial bench cannot start yet: no COM/Serial device is currently enumerated and the Smart Ward Hub workspace is not present on the checked attached path.

The new `serial_bench_runner.py` therefore remains dry-run-first. It will not infer a port or open one without an explicit port and the exact confirmation phrase `I_HAVE_A_NONPRODUCTION_LOOPBACK`. A non-production USB-serial loopback fixture or controlled gateway must be connected before physical validation can begin.

This inventory is host evidence only. It does not establish Acer hardware reliability, serial-driver compatibility, power-loss behavior, network segmentation or clinical validation.
