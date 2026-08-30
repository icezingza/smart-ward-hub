"""Synthetic concurrent wristband telemetry streamer for local Hub testing."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from math import sin
from pathlib import Path
from time import perf_counter
from typing import Literal
from urllib.parse import urlparse

import httpx

ScenarioName = Literal["normal", "cardiac_distress", "silent_fall", "mixed"]


@dataclass(frozen=True)
class VirtualTelemetry:
    device_id: str
    bed_no: str
    sequence: int
    timestamp: str
    heart_rate: float
    spo2: float
    skin_temp: float
    accel_x: float
    accel_y: float
    accel_z: float
    gyro_x: float
    gyro_y: float
    gyro_z: float
    battery_pct: float
    scenario: str
    scenario_phase: str

    def hub_payload(self) -> dict[str, object]:
        """Map extended synthetic telemetry to the current TelemetryPacket v1."""
        return {
            "device_id": self.device_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "ppg": 0.82,
            "accel_x": self.accel_x,
            "accel_y": self.accel_y,
            "accel_z": self.accel_z,
            "skin_temp": self.skin_temp,
            "battery_pct": self.battery_pct,
            "heart_rate": self.heart_rate,
            "spo2": self.spo2,
        }


def scenario_for_bed(index: int, requested: ScenarioName) -> str:
    if requested != "mixed":
        return requested
    return ("normal", "cardiac_distress", "silent_fall")[index % 3]


def build_packet(*, bed_index: int, sequence: int, scenario: str, timestamp: datetime) -> VirtualTelemetry:
    phase = sequence % 6
    accel_x = 0.02 * sin(sequence)
    accel_y = 0.02 * sin(sequence / 2)
    accel_z = 1.0
    gyro_x = 0.01 * sin(sequence)
    gyro_y = 0.01 * sin(sequence / 2)
    gyro_z = 0.01 * sin(sequence / 3)
    heart_rate = 70.0 + phase
    spo2 = 98.0
    scenario_phase = "normal"

    if scenario == "cardiac_distress":
        heart_rate = 142.0 if sequence % 2 else 42.0
        spo2 = 88.0
        scenario_phase = "tachycardia" if sequence % 2 else "bradycardia"
    elif scenario == "silent_fall":
        if sequence == 2:
            accel_x, accel_y, accel_z = 0.0, 0.0, 3.2
            gyro_x, gyro_y, gyro_z = 1.8, 1.6, 1.4
            scenario_phase = "impact"
        elif sequence >= 3:
            accel_x, accel_y, accel_z = 0.0, 0.0, 1.0
            gyro_x = gyro_y = gyro_z = 0.0
            scenario_phase = "motionless_after_impact"

    return VirtualTelemetry(
        device_id=f"vw-sim-{bed_index + 1:03d}",
        bed_no=f"SIM-BED-{bed_index + 1:03d}",
        sequence=sequence,
        timestamp=timestamp.isoformat(),
        heart_rate=heart_rate,
        spo2=spo2,
        skin_temp=36.7,
        accel_x=accel_x,
        accel_y=accel_y,
        accel_z=accel_z,
        gyro_x=gyro_x,
        gyro_y=gyro_y,
        gyro_z=gyro_z,
        battery_pct=max(0.0, 96.0 - sequence * 0.1),
        scenario=scenario,
        scenario_phase=scenario_phase,
    )


def build_stream(*, bed_count: int = 30, sample_count: int = 8, interval_seconds: float = 1.0,
                 scenario: ScenarioName = "mixed", start_time: datetime | None = None) -> list[list[VirtualTelemetry]]:
    if not 1 <= bed_count <= 200:
        raise ValueError("bed_count must be between 1 and 200")
    if sample_count < 7:
        raise ValueError("sample_count must be at least 7 for the silent-fall stillness window")
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than zero")
    started = start_time or datetime.now(timezone.utc)
    return [[build_packet(
        bed_index=bed_index,
        sequence=sequence,
        scenario=scenario_for_bed(bed_index, scenario),
        timestamp=started + timedelta(seconds=interval_seconds * (sequence - 1)),
    ) for sequence in range(1, sample_count + 1)] for bed_index in range(bed_count)]


def _validate_loopback_url(hub_url: str) -> None:
    parsed = urlparse(hub_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("--send accepts only an http loopback Hub URL")


def _summary(streams: list[list[VirtualTelemetry]], *, statuses: list[int], latency_ms: list[float],
            errors: list[dict[str, object]], network_mode: str) -> dict[str, object]:
    events = [event for stream in streams for event in stream]
    scenarios: dict[str, int] = {}
    for event in events:
        scenarios[event.scenario] = scenarios.get(event.scenario, 0) + 1
    ordered = sorted(latency_ms)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)] if ordered else None
    return {
        "streamer": "virtual-wristband-telemetry-streamer-v1",
        "data_classification": "SYNTHETIC_NON_CLINICAL",
        "network_mode": network_mode,
        "beds": len(streams),
        "samples_per_bed": len(streams[0]) if streams else 0,
        "total_samples": len(events),
        "scenarios": scenarios,
        "accepted_statuses": sum(200 <= status < 300 for status in statuses),
        "error_count": len(errors),
        "latency_ms": {"sample_count": len(ordered), "p50": ordered[len(ordered) // 2] if ordered else None,
                       "p95": p95, "max": max(ordered) if ordered else None,
                       "note": "Measured only for loopback HTTP sends; dry-run has no network latency."},
        "silent_fall_contract": {"impact_g": 3.2, "stillness_seconds": ">= 5 at the default 1-second interval"},
        "errors": errors,
    }


def run_dry_run(streams: list[list[VirtualTelemetry]]) -> dict[str, object]:
    return _summary(streams, statuses=[], latency_ms=[], errors=[], network_mode="dry_run")


async def stream_to_hub(streams: list[list[VirtualTelemetry]], *, hub_url: str, token: str,
                        interval_seconds: float) -> dict[str, object]:
    _validate_loopback_url(hub_url)
    headers = {"Authorization": f"Bearer {token}", "X-Smart-Ward-Simulator": "synthetic-non-clinical"}
    latency_ms: list[float] = []
    statuses: list[int] = []
    errors: list[dict[str, object]] = []
    async with httpx.AsyncClient(base_url=hub_url.rstrip("/"), headers=headers, timeout=5.0) as client:
        async def stream_one(events: list[VirtualTelemetry]) -> None:
            first = events[0]
            pairing = await client.post("/api/v1/pairing", json={
                "patient_token": f"synthetic-patient-{first.device_id}", "bed_no": first.bed_no,
                "device_id": first.device_id, "risk_level": "High" if first.scenario != "normal" else "Low",
            })
            if pairing.status_code >= 400:
                errors.append({"device_id": first.device_id, "stage": "pairing", "status": pairing.status_code})
                return
            for event in events:
                started = perf_counter()
                response = await client.post("/api/v1/telemetry", json=event.hub_payload())
                latency_ms.append((perf_counter() - started) * 1000)
                statuses.append(response.status_code)
                if response.status_code >= 400:
                    errors.append({"device_id": event.device_id, "sequence": event.sequence, "status": response.status_code})
                await asyncio.sleep(interval_seconds)
        await asyncio.gather(*(stream_one(events) for events in streams))
    return _summary(streams, statuses=statuses, latency_ms=latency_ms, errors=errors, network_mode="loopback")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream synthetic wristbands to a loopback Smart Ward Hub.")
    parser.add_argument("--beds", type=int, default=30)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--scenario", choices=("normal", "cardiac_distress", "silent_fall", "mixed"), default="mixed")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--hub-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", help="Local bearer token with pairing:write and telemetry:write.")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> dict[str, object]:
    streams = build_stream(bed_count=args.beds, sample_count=args.samples,
                           interval_seconds=args.interval_seconds, scenario=args.scenario)
    if not args.send:
        return run_dry_run(streams)
    if not args.token:
        raise SystemExit("--send requires --token; dry-run never needs a token")
    return await stream_to_hub(streams, hub_url=args.hub_url, token=args.token, interval_seconds=args.interval_seconds)


def main() -> int:
    args = parse_args()
    report = asyncio.run(main_async(args))
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
