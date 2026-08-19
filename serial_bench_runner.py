from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
from typing import Any

from serial_framing import ETX, SerialFrameCodec


PHYSICAL_CONFIRMATION = "I_HAVE_A_NONPRODUCTION_LOOPBACK"


@dataclass(frozen=True)
class PortInfo:
    device: str
    description: str
    hwid_present: bool


@dataclass(frozen=True)
class BenchConfig:
    port: str | None
    baudrate: int
    timeout_seconds: float
    max_payload: int
    output: Path
    dry_run: bool
    confirm_physical: str | None


def _port_inventory() -> tuple[str, list[PortInfo]]:
    try:
        from serial.tools import list_ports  # type: ignore
    except ImportError:
        return "pyserial_unavailable", []
    ports = [
        PortInfo(
            device=str(port.device),
            description=str(port.description or ""),
            hwid_present=bool(port.hwid),
        )
        for port in list_ports.comports()
    ]
    return "pyserial_available", ports


def _base_evidence(config: BenchConfig, inventory_status: str, ports: list[PortInfo]) -> dict[str, Any]:
    return {
        "run_id": f"serial-bench-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "mode": "dry_run" if config.dry_run else "physical_loopback",
        "status": "DRY_RUN_ONLY" if config.dry_run else "NOT_STARTED",
        "host_platform": platform.platform(),
        "python_version": platform.python_version(),
        "project": "smart-ward-hub",
        "adapter": "serial_framing.py",
        "inventory_status": inventory_status,
        "ports": [asdict(port) for port in ports],
        "selected_port": config.port,
        "baudrate": config.baudrate,
        "timeout_seconds": config.timeout_seconds,
        "max_payload": config.max_payload,
        "physical_hardware_validation": "PENDING",
        "production_network_validation": "PENDING",
        "patient_data_used": False,
        "private_key_used": False,
        "raw_frames_recorded": False,
    }


def _synthetic_payload() -> bytes:
    payload = {
        "packet": {
            "schema_version": "1.0",
            "device_id": "device-serial-bench-001",
            "sequence": 1,
            "timestamp": "2026-08-20T00:00:00Z",
            "ppg": 0.82,
            "accel_x": 0.02,
            "accel_y": 0.01,
            "accel_z": 1.01,
            "skin_temp": 36.7,
            "battery_pct": 87.0,
            "heart_rate": 72.0,
            "spo2": 98.0,
        },
        "source_device_id": "device-serial-bench-001",
        "key_id": "synthetic-key-id-only",
        "signature_b64": "synthetic-signature-placeholder",
        "mapping_version": "serial-json-v1",
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _dry_run(config: BenchConfig, evidence: dict[str, Any]) -> dict[str, Any]:
    codec = SerialFrameCodec(max_payload=config.max_payload)
    frame = codec.encode(_synthetic_payload(), max_payload=config.max_payload)
    events = codec.feed(frame[:1]) + codec.feed(frame[1:])
    evidence["dry_run_codec"] = {
        "frame_length": len(frame),
        "event_kinds": [event.kind for event in events],
        "codec_buffered_bytes": codec.buffered_bytes,
        "result": "PASS" if [event.kind for event in events] == ["frame"] else "FAIL",
    }
    evidence["status"] = "DRY_RUN_ONLY"
    evidence["next_action"] = "Connect a non-production loopback fixture, then rerun with --port and --confirm-physical I_HAVE_A_NONPRODUCTION_LOOPBACK."
    return evidence


def _physical_loopback(config: BenchConfig, evidence: dict[str, Any]) -> dict[str, Any]:
    if not config.port:
        evidence["status"] = "BLOCKED_NO_PORT"
        evidence["failure_class"] = "port_required"
        return evidence
    if config.confirm_physical != PHYSICAL_CONFIRMATION:
        evidence["status"] = "BLOCKED_CONFIRMATION_REQUIRED"
        evidence["failure_class"] = "physical_confirmation_required"
        return evidence
    try:
        import serial  # type: ignore
    except ImportError:
        evidence["status"] = "BLOCKED_DEPENDENCY"
        evidence["failure_class"] = "pyserial_required_for_physical_run"
        return evidence

    frame = SerialFrameCodec.encode(_synthetic_payload(), max_payload=config.max_payload)
    codec = SerialFrameCodec(max_payload=config.max_payload)
    try:
        with serial.Serial(config.port, config.baudrate, timeout=config.timeout_seconds, write_timeout=config.timeout_seconds) as connection:
            connection.reset_input_buffer()
            connection.write(frame)
            connection.flush()
            received = connection.read_until(bytes([ETX]))
    except Exception as exc:  # pragma: no cover - hardware-only path
        evidence["status"] = "PHYSICAL_IO_ERROR"
        evidence["failure_class"] = type(exc).__name__
        return evidence

    events = codec.feed(received)
    evidence["physical_result"] = {
        "received_bytes": len(received),
        "event_kinds": [event.kind for event in events],
        "frame_round_trip": any(event.kind == "frame" for event in events),
        "raw_bytes_recorded": False,
    }
    evidence["status"] = "PASSED" if evidence["physical_result"]["frame_round_trip"] else "FAILED"
    return evidence


def run(config: BenchConfig) -> dict[str, Any]:
    inventory_status, ports = _port_inventory()
    evidence = _base_evidence(config, inventory_status, ports)
    if config.dry_run:
        return _dry_run(config, evidence)
    return _physical_loopback(config, evidence)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed Smart Ward Serial bench runner")
    parser.add_argument("--list-ports", action="store_true", help="List detected ports and exit without opening one")
    parser.add_argument("--port", help="Explicit COM/tty port; never inferred")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--max-payload", type=int, default=4096)
    parser.add_argument("--output", type=Path, default=Path("serial_bench_evidence.json"))
    parser.add_argument("--dry-run", action="store_true", help="Default-safe mode; do not open a port")
    parser.add_argument("--confirm-physical", help=f"Required exact confirmation: {PHYSICAL_CONFIRMATION}")
    args = parser.parse_args()
    dry_run = args.dry_run or not args.confirm_physical
    config = BenchConfig(
        port=args.port,
        baudrate=args.baudrate,
        timeout_seconds=args.timeout,
        max_payload=args.max_payload,
        output=args.output,
        dry_run=dry_run,
        confirm_physical=args.confirm_physical,
    )
    if args.list_ports:
        status, ports = _port_inventory()
        print(json.dumps({"inventory_status": status, "ports": [asdict(port) for port in ports]}, indent=2))
        return 0
    evidence = run(config)
    config.output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["status"] in {"DRY_RUN_ONLY", "PASSED", "BLOCKED_NO_PORT", "BLOCKED_CONFIRMATION_REQUIRED", "BLOCKED_DEPENDENCY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
