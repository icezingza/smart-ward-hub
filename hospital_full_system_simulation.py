"""Synthetic end-to-end hospital simulation through the local FastAPI Hub.

The default profile represents five synthetic wards with forty beds each. It is
configurable because a real hospital's ward count and capacity must be supplied
by an authorized site owner, not guessed by this repository.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any


def _risk_case(bed_index: int) -> str:
    return {
        2: "suspected_fall",
        5: "vital_anomaly",
        8: "device_disconnected",
        12: "perimeter_capability_gap",
        20: "blood_pressure_capability_gap",
    }.get(bed_index, "normal")


def _configure_isolated_runtime(root: Path, device_count: int) -> None:
    os.environ.update(
        {
            "SW_AUTH_TOKENS_JSON": '{"hospital-sim-token":["admin"]}',
            "SW_DEVICE_TRUST_MODE": "disabled",
            "SW_AUTO_CREATE_DB": "true",
            "SW_SEED_DATA": "false",
            "SW_RATE_LIMIT_PER_MINUTE": "100000",
            "SW_TELEMETRY_MAX_DEVICES": str(device_count),
            "SW_TELEMETRY_BUFFER_MAX_SAMPLES": "32",
            "SW_TELEMETRY_CHECKPOINT_EVERY": "64",
            "SW_DATABASE_PATH": str(root / "hospital-sim.db"),
            "SW_TELEMETRY_STATE_PATH": str(root / "hospital-sim-state.json"),
            "SW_AUDIT_LOG_PATH": str(root / "hospital-sim-audit.jsonl"),
        }
    )


def _packet(device_id: str, sequence: int, risk_case: str, timestamp: datetime) -> dict[str, object]:
    return {
        "device_id": device_id,
        "sequence": sequence,
        "timestamp": timestamp.isoformat(),
        "ppg": 0.82,
        "accel_x": 0.0,
        "accel_y": 0.0,
        "accel_z": 3.0 if risk_case == "suspected_fall" and sequence == 2 else 1.0,
        "skin_temp": 36.7,
        "battery_pct": 90.0 - sequence * 0.1,
        "heart_rate": 130.0 if risk_case == "vital_anomaly" else 72.0,
        "spo2": 88.0 if risk_case == "vital_anomaly" else 98.0,
    }


def run_hospital_simulation(*, ward_count: int = 5, beds_per_ward: int = 40, ticks: int = 8) -> dict[str, Any]:
    if not 1 <= ward_count <= 20:
        raise ValueError("ward_count must be between 1 and 20")
    if not 20 <= beds_per_ward <= 40:
        raise ValueError("beds_per_ward must be between 20 and 40")
    if ticks < 7:
        raise ValueError("ticks must be at least 7 to evaluate the fall pattern")
    device_count = ward_count * beds_per_ward

    # Imports occur after environment setup so this process cannot touch the real Hub state.
    with tempfile.TemporaryDirectory(prefix="smart-ward-hospital-sim-") as directory:
        root = Path(directory)
        _configure_isolated_runtime(root, device_count)
        from fastapi.testclient import TestClient
        from database import SessionLocal, engine
        from main import ACTIVE_PAIRINGS_CACHE, RATE_LIMITER, TELEMETRY_STORE, app
        import models

        ACTIVE_PAIRINGS_CACHE.clear()
        RATE_LIMITER.clear()
        TELEMETRY_STORE.clear()
        start = datetime(2026, 8, 29, tzinfo=timezone.utc)
        synthetic_rows: list[dict[str, str]] = []
        with SessionLocal() as db:
            for ward_index in range(1, ward_count + 1):
                ward_id = f"SIM-W{ward_index:02d}"
                for bed_index in range(1, beds_per_ward + 1):
                    bed_no = f"{ward_id}-B{bed_index:02d}"
                    device_id = f"hospital-sim-{ward_index:02d}-{bed_index:02d}"
                    patient_token = f"ptok-hospital-sim-{ward_index:02d}-{bed_index:02d}"
                    db.add_all(
                        [
                            models.Patient(patient_token=patient_token),
                            models.Bed(bed_no=bed_no, ward_id=ward_id),
                            models.Device(device_id=device_id),
                        ]
                    )
                    synthetic_rows.append(
                        {
                            "ward_id": ward_id,
                            "bed_no": bed_no,
                            "device_id": device_id,
                            "patient_token": patient_token,
                            "risk_case": _risk_case(bed_index),
                        }
                    )
            db.commit()

        headers = {"Authorization": "Bearer hospital-sim-token"}
        accepted_packets = 0
        server_sync: list[dict[str, object]] = []
        warnings: list[dict[str, str]] = []
        with TestClient(app, headers=headers) as client:
            for row in synthetic_rows:
                response = client.post(
                    "/api/v1/pairing",
                    json={
                        "patient_token": row["patient_token"],
                        "bed_no": row["bed_no"],
                        "device_id": row["device_id"],
                        "risk_level": "High" if row["risk_case"] in {"suspected_fall", "vital_anomaly"} else "Medium",
                    },
                )
                if response.status_code != 200:
                    raise AssertionError(f"pairing_failed:{row['bed_no']}:{response.status_code}")

            for tick in range(ticks):
                for row in synthetic_rows:
                    if row["risk_case"] == "device_disconnected" and tick >= 1:
                        continue
                    response = client.post(
                        "/api/v1/telemetry",
                        json=_packet(row["device_id"], tick + 1, row["risk_case"], start + timedelta(seconds=tick)),
                    )
                    if response.status_code != 200:
                        raise AssertionError(f"telemetry_failed:{row['bed_no']}:{tick}:{response.status_code}")
                    accepted_packets += 1
                if tick == 3:
                    warnings.extend(
                        {
                            "ward_id": row["ward_id"],
                            "bed_no": row["bed_no"],
                            "warning": "DEVICE_PERIMETER_WARNING" if row["risk_case"] == "perimeter_capability_gap" else "BLOOD_PRESSURE_SENSOR_UNSUPPORTED",
                            "action": "manual_check_required" if row["risk_case"] == "perimeter_capability_gap" else "manual_bp_measurement_required",
                        }
                        for row in synthetic_rows
                        if row["risk_case"] in {"perimeter_capability_gap", "blood_pressure_capability_gap"}
                    )

            for ward_index in range(1, ward_count + 1):
                source = next(row for row in synthetic_rows if row["ward_id"] == f"SIM-W{ward_index:02d}" and row["risk_case"] == "normal")
                aggregate = client.post(f"/api/v1/telemetry/aggregate/{source['device_id']}")
                if aggregate.status_code != 200:
                    raise AssertionError(f"aggregate_failed:{source['bed_no']}:{aggregate.status_code}")
                handover = client.post(
                    f"/api/v1/handover/{source['device_id']}",
                    json={"start_time": start.isoformat(), "end_time": (start + timedelta(minutes=1)).isoformat()},
                )
                if handover.status_code != 200:
                    raise AssertionError(f"handover_failed:{source['bed_no']}:{handover.status_code}")
                bundle_id = handover.json()["bundle_id"]
                retained = client.post(
                    f"/api/v1/handover/{source['device_id']}/sync/{bundle_id}",
                    json={"acknowledged": False, "status_code": 503, "error_message": "synthetic_server_unavailable"},
                )
                if retained.status_code != 200 or retained.json()["data"]["sync_status"] != "RETAINED_FOR_RETRY":
                    raise AssertionError(f"server_retry_boundary_failed:{source['bed_no']}")
                acknowledged = client.post(
                    f"/api/v1/handover/{source['device_id']}/sync/{bundle_id}",
                    json={
                        "acknowledged": True,
                        "status_code": 200,
                        "acknowledged_bundle_id": bundle_id,
                        "acknowledgment_id": f"hospital-sim-ack-{ward_index:02d}",
                        "receiving_system": "synthetic-hospital-server",
                        "server_time": (start + timedelta(minutes=2)).isoformat(),
                        "accepted_version": "R4",
                        "accepted_profile": "synthetic-observation-v1",
                    },
                )
                if acknowledged.status_code != 200 or acknowledged.json()["data"]["sync_status"] != "ACKNOWLEDGED":
                    raise AssertionError(f"server_ack_boundary_failed:{source['bed_no']}")
                server_sync.append({"ward_id": source["ward_id"], "bundle_id": bundle_id, "retained_on_503": True, "acknowledged_after_structured_ack": True})

        with SessionLocal() as db:
            alert_count = db.query(models.Alert).count()
            package_count = db.query(models.ForensicPackage).count()
            active_pairings = db.query(models.Pairing).filter(models.Pairing.is_active.is_(True)).count()

        expected_packets = device_count * ticks - ward_count * (ticks - 1)
        expected_alerts = ward_count * 2
        engine.dispose()
        return {
            "schema_version": "smart-ward-hub-hospital-full-system-simulation-v1",
            "evidence_class": "LOCAL_SYNTHETIC_FASTAPI_SIMULATION",
            "hospital_profile": {"ward_count": ward_count, "beds_per_ward": beds_per_ward, "hub_count": ward_count, "total_beds": device_count},
            "accepted_packets": accepted_packets,
            "expected_packets": expected_packets,
            "active_pairings": active_pairings,
            "alert_count": alert_count,
            "forensic_package_count": package_count,
            "warnings": warnings,
            "server_sync": server_sync,
            "expected_results_matched": accepted_packets == expected_packets and active_pairings == device_count and alert_count == expected_alerts and package_count == expected_alerts and len(server_sync) == ward_count,
            "patient_data_used": False,
            "hardware_contacted": False,
            "external_server_contacted": False,
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "limitations": [
                "Each synthetic ward has one logical Hub; this does not prove a physical Hub capacity or hospital-wide network topology.",
                "Blood pressure, location and RSSI are not fields in TelemetryPacket v1 and therefore remain capability gaps, not clinical alerts.",
                "The server acknowledgement is a local synthetic contract response; it is not a real HIS, FHIR, mTLS, or OIDC integration.",
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an isolated synthetic multi-ward FastAPI simulation.")
    parser.add_argument("--wards", type=int, default=5)
    parser.add_argument("--beds-per-ward", type=int, default=40)
    parser.add_argument("--ticks", type=int, default=8)
    args = parser.parse_args()
    report = run_hospital_simulation(ward_count=args.wards, beds_per_ward=args.beds_per_ward, ticks=args.ticks)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["expected_results_matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
