"""Synthetic-only Smart Watch telemetry simulator for local Hub development.

The simulator never creates patient data and does not send network traffic unless
``--send`` is supplied.  Even then, it accepts loopback Hub URLs only.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from typing import Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from schemas import TelemetryPacket


ScenarioName = Literal["normal", "replay", "out_of_order", "offline_reconnect"]
EventKind = Literal["telemetry", "disconnect", "reconnect"]
TelemetrySender = Callable[[TelemetryPacket], int]


@dataclass(frozen=True)
class SimulatedEvent:
    kind: EventKind
    expected_status: int | None
    note: str
    packet: TelemetryPacket | None = None

    def evidence(self) -> dict[str, object]:
        result: dict[str, object] = {
            "kind": self.kind,
            "expected_status": self.expected_status,
            "note": self.note,
        }
        if self.packet is not None:
            result["device_id"] = self.packet.device_id
            result["sequence"] = self.packet.sequence
            result["timestamp"] = self.packet.timestamp.isoformat()
        return result


def _packet(device_id: str, sequence: int, timestamp: datetime) -> TelemetryPacket:
    """Return deterministic, bounded telemetry with no patient identity."""
    phase = sequence % 5
    return TelemetryPacket(
        device_id=device_id,
        sequence=sequence,
        timestamp=timestamp,
        ppg=0.80 + phase * 0.01,
        accel_x=0.01 * phase,
        accel_y=0.02 * phase,
        accel_z=1.0 + 0.01 * phase,
        skin_temp=36.5 + 0.05 * phase,
        battery_pct=max(0.0, 95.0 - sequence * 0.05),
        heart_rate=70.0 + phase,
        spo2=98.0,
    )


def build_scenario(
    scenario: ScenarioName,
    *,
    device_id: str = "smartwatch-sim-001",
    sample_count: int = 5,
    start_sequence: int = 1,
    start_time: datetime | None = None,
    interval_seconds: float = 1.0,
) -> list[SimulatedEvent]:
    """Create a reproducible stream for the same ingress contract as a watch."""
    if sample_count < 1:
        raise ValueError("sample_count must be at least 1")
    if start_sequence < 0:
        raise ValueError("start_sequence must be zero or greater")
    if interval_seconds < 0:
        raise ValueError("interval_seconds must be zero or greater")
    if scenario not in {"normal", "replay", "out_of_order", "offline_reconnect"}:
        raise ValueError(f"unsupported scenario: {scenario}")

    # Validate the device identifier using the production packet contract.
    started = start_time or datetime.now(timezone.utc)
    packets = [
        _packet(device_id, start_sequence + offset, started + timedelta(seconds=interval_seconds * offset))
        for offset in range(sample_count)
    ]
    events = [
        SimulatedEvent("telemetry", 200, "synthetic telemetry accepted", packet)
        for packet in packets
    ]

    if scenario == "replay":
        events.append(SimulatedEvent("telemetry", 409, "synthetic duplicate sequence must be rejected", packets[-1]))
    elif scenario == "out_of_order":
        sequence = packets[-1].sequence - 1 if len(packets) > 1 else packets[-1].sequence
        events.append(
            SimulatedEvent(
                "telemetry",
                409,
                "synthetic out-of-order sequence must be rejected",
                _packet(device_id, sequence, packets[-1].timestamp + timedelta(seconds=interval_seconds)),
            )
        )
    elif scenario == "offline_reconnect":
        midpoint = max(1, len(events) // 2)
        events.insert(midpoint, SimulatedEvent("disconnect", None, "synthetic network interruption; no packet sent"))
        events.insert(midpoint + 1, SimulatedEvent("reconnect", None, "synthetic reconnect; sequence remains monotonic"))

    return events


def run_scenario(events: list[SimulatedEvent], sender: TelemetrySender | None = None) -> dict[str, object]:
    """Run a scenario through an optional ingress sender and verify expectations."""
    results: list[dict[str, object]] = []
    passed = True
    for event in events:
        row = event.evidence()
        if event.kind == "telemetry" and sender is not None:
            assert event.packet is not None
            actual_status = sender(event.packet)
            row["actual_status"] = actual_status
            row["passed"] = actual_status == event.expected_status
            passed = passed and bool(row["passed"])
        elif event.kind == "telemetry":
            row["actual_status"] = "NOT_SENT"
            row["passed"] = True
        else:
            row["actual_status"] = "NO_NETWORK_REQUEST"
            row["passed"] = True
        results.append(row)
    return {
        "simulator": "smartwatch-simulator-v1",
        "data_classification": "SYNTHETIC_NON_CLINICAL",
        "network_mode": "sent" if sender is not None else "dry_run",
        "passed": passed,
        "events": results,
    }


def _local_telemetry_sender(base_url: str, token: str) -> TelemetrySender:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("--send accepts only an http loopback Hub URL")
    endpoint = f"{base_url.rstrip('/')}/api/v1/telemetry"

    def send(packet: TelemetryPacket) -> int:
        body = json.dumps(packet.model_dump(mode="json"), separators=(",", ":")).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Smart-Ward-Simulator": "synthetic-non-clinical",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=5) as response:  # nosec B310: loopback validated above
                return response.status
        except HTTPError as error:
            return error.code
        except URLError as error:
            raise RuntimeError(f"Hub connection failed: {error.reason}") from error

    return send


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run synthetic-only Smart Watch telemetry scenarios.")
    parser.add_argument("--scenario", choices=("normal", "replay", "out_of_order", "offline_reconnect"), default="normal")
    parser.add_argument("--device-id", default="smartwatch-sim-001")
    parser.add_argument("--sample-count", type=int, default=5)
    parser.add_argument("--start-sequence", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--send", action="store_true", help="Send to a local Hub instead of dry-run output.")
    parser.add_argument("--hub-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", help="Local development bearer token with telemetry:write scope.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.send and not args.token:
        raise SystemExit("--send requires --token; dry-run never needs a token")
    events = build_scenario(
        args.scenario,
        device_id=args.device_id,
        sample_count=args.sample_count,
        start_sequence=args.start_sequence,
        interval_seconds=args.interval_seconds,
    )
    sender = _local_telemetry_sender(args.hub_url, args.token) if args.send else None
    print(json.dumps(run_scenario(events, sender), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
