"""Synthetic 40-bed ward simulation for one local Hub.

It exercises the same telemetry schema, bounded Edge store and prototype triage
as the Hub.  It intentionally records unsupported sensor capabilities instead
of inventing blood-pressure or location data that the contract does not carry.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Literal

from edge_runtime import EdgeTelemetryStore
from schemas import TelemetryPacket
from triage_engine import evaluate_telemetry_triage


RiskCase = Literal["normal", "suspected_fall", "vital_anomaly", "disconnected", "perimeter_warning", "hypotension_capability_gap"]


@dataclass(frozen=True)
class BedSimulation:
    bed_no: str
    device_id: str
    risk_case: RiskCase
    risk_level: str = "Low"


def build_ward(bed_count: int = 40) -> list[BedSimulation]:
    if not 1 <= bed_count <= 40:
        raise ValueError("bed_count must be between 1 and 40 for the one-Hub simulator")
    injected: dict[int, RiskCase] = {
        2: "suspected_fall",
        5: "vital_anomaly",
        8: "disconnected",
        12: "perimeter_warning",
        20: "hypotension_capability_gap",
    }
    return [
        BedSimulation(
            bed_no=f"SIM-W01-B{index:02d}",
            device_id=f"smartwatch-ward-sim-{index:02d}",
            risk_case=injected.get(index, "normal"),
            risk_level="High" if index in {2, 5} else "Medium" if index in {8, 12, 20} else "Low",
        )
        for index in range(1, bed_count + 1)
    ]


def _packet(bed: BedSimulation, sequence: int, timestamp: datetime) -> TelemetryPacket:
    accel_z = 3.0 if bed.risk_case == "suspected_fall" and sequence == 2 else 1.0
    heart_rate = 130.0 if bed.risk_case == "vital_anomaly" else 72.0
    spo2 = 88.0 if bed.risk_case == "vital_anomaly" else 98.0
    return TelemetryPacket(
        device_id=bed.device_id,
        sequence=sequence,
        timestamp=timestamp,
        ppg=0.82,
        accel_x=0.0,
        accel_y=0.0,
        accel_z=accel_z,
        skin_temp=36.7,
        battery_pct=90.0 - sequence * 0.1,
        heart_rate=heart_rate,
        spo2=spo2,
    )


def run_simulation(*, bed_count: int = 40, ticks: int = 8, stale_after_ticks: int = 2) -> dict[str, Any]:
    if ticks < 6:
        raise ValueError("ticks must be at least 6 so the fall pattern can be evaluated")
    if stale_after_ticks < 1:
        raise ValueError("stale_after_ticks must be at least 1")
    ward = build_ward(bed_count)
    store = EdgeTelemetryStore(max_samples=ticks, max_devices=bed_count, state_path=None)
    start = datetime(2026, 8, 29, tzinfo=timezone.utc)
    last_received_tick: dict[str, int] = {}
    alerts: dict[str, str] = {}
    warnings: list[dict[str, str]] = []
    accepted_packets = 0

    for tick in range(ticks):
        for bed in ward:
            # Device 8 stops transmitting after its initial heartbeat.
            if bed.risk_case == "disconnected" and tick >= 1:
                continue
            packet = _packet(bed, tick + 1, start + timedelta(seconds=tick))
            sample = {
                "sequence": packet.sequence,
                "timestamp": packet.timestamp,
                "accel_x": packet.accel_x,
                "accel_y": packet.accel_y,
                "accel_z": packet.accel_z,
                "g_force": (packet.accel_x**2 + packet.accel_y**2 + packet.accel_z**2) ** 0.5,
                "skin_temp": packet.skin_temp,
                "battery_pct": packet.battery_pct,
                "heart_rate": packet.heart_rate,
                "spo2": packet.spo2,
            }
            result = store.append(packet.device_id, sample, packet.sequence)
            if not result.accepted:
                raise AssertionError(f"unexpected_rejection:{bed.device_id}:{result.reason}")
            accepted_packets += 1
            last_received_tick[bed.device_id] = tick
            signal = evaluate_telemetry_triage(store.snapshot(packet.device_id), bed.risk_level)
            if signal is not None:
                alerts[bed.bed_no] = signal["alert_type"]

        for bed in ward:
            if bed.risk_case == "disconnected" and tick - last_received_tick.get(bed.device_id, -ticks) >= stale_after_ticks:
                warning = {"bed_no": bed.bed_no, "warning": "DEVICE_DISCONNECTED_STALE", "action": "manual_check_required"}
                if warning not in warnings:
                    warnings.append(warning)
            if bed.risk_case == "perimeter_warning" and tick == 3:
                warnings.append({"bed_no": bed.bed_no, "warning": "DEVICE_PERIMETER_WARNING", "action": "manual_check_required"})
            if bed.risk_case == "hypotension_capability_gap" and tick == 0:
                warnings.append({"bed_no": bed.bed_no, "warning": "BLOOD_PRESSURE_SENSOR_UNSUPPORTED", "action": "manual_bp_measurement_required"})

    expected_alerts = {"SIM-W01-B02": "FALL", "SIM-W01-B05": "VITAL_ANOMALY"}
    expected_warnings = {
        "SIM-W01-B08": "DEVICE_DISCONNECTED_STALE",
        "SIM-W01-B12": "DEVICE_PERIMETER_WARNING",
        "SIM-W01-B20": "BLOOD_PRESSURE_SENSOR_UNSUPPORTED",
    }
    actual_warnings = {item["bed_no"]: item["warning"] for item in warnings}
    return {
        "schema_version": "smart-ward-hub-ward-scale-simulation-v1",
        "evidence_class": "LOCAL_SYNTHETIC_SOFTWARE_SIMULATION",
        "hub_count": 1,
        "bed_count": bed_count,
        "ticks": ticks,
        "accepted_packets": accepted_packets,
        "max_devices_configured": store.stats()["max_devices"],
        "alerts": alerts,
        "warnings": warnings,
        "risk_cases": [asdict(bed) for bed in ward if bed.risk_case != "normal"],
        "expected_results_matched": alerts == expected_alerts and actual_warnings == expected_warnings,
        "patient_data_used": False,
        "hardware_contacted": False,
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "limitations": [
            "Blood pressure is not in TelemetryPacket v1; low-blood-pressure detection is not simulated as an alert.",
            "Location/RSSI is not in TelemetryPacket v1; perimeter state is a synthetic operational warning only.",
            "Fall and vital anomaly outputs are non-diagnostic prototype signals, not clinical conclusions.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a synthetic ward-scale simulation for one Hub.")
    parser.add_argument("--beds", type=int, default=40)
    parser.add_argument("--ticks", type=int, default=8)
    args = parser.parse_args()
    report = run_simulation(bed_count=args.beds, ticks=args.ticks)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0 if report["expected_results_matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
