"""
Virtual Hardware Hub Bridge for IPD Smart Sentinel.
Simulates real-time telemetry streaming from virtual wristbands to Smart Ward Hub
and broadcasts via WebSockets for the Mobile Bedside PDA companion.
"""

import asyncio
from datetime import datetime, timezone
import logging
import math
import random
import time
from typing import Dict, Any, List

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VirtualHardwareBridge")

HUB_BASE_URL = "http://127.0.0.1:8000"
HUB_AUTH_HEADER = {"Authorization": "Bearer test-token"}


class VirtualWristband:
    def __init__(self, bed_id: str, patient_token: str, device_uid: str, placement: str = "WRIST"):
        self.bed_id = bed_id
        self.patient_token = patient_token
        self.device_uid = device_uid
        self.placement = placement
        self.sequence_number = int(time.time() * 10) % 1_000_000
        self.battery_pct = 95
        self.base_hr = random.randint(68, 78)
        self.base_spo2 = random.randint(97, 99)
        self.is_critical = False
        self.critical_type = None

    def generate_packet(self) -> Dict[str, Any]:
        self.sequence_number += 1
        now = time.time()

        if self.is_critical and self.critical_type == "FALL":
            # Impact acceleration followed by immobility
            g_force = 2.1
            hr = self.base_hr + 25
            spo2 = self.base_spo2 - 2
        elif self.is_critical and self.critical_type == "CARDIAC":
            g_force = 1.0
            hr = 155
            spo2 = 88
        else:
            # Normal physiological fluctuation
            g_force = 1.0 + random.uniform(-0.05, 0.05)
            hr = int(self.base_hr + 3 * math.sin(now / 10.0) + random.uniform(-1, 1))
            spo2 = int(min(100, max(94, self.base_spo2 + random.uniform(-1, 1))))

        # Slowly discharge battery
        if random.random() < 0.05 and self.battery_pct > 15:
            self.battery_pct -= 1

        iso_now = datetime.now(timezone.utc).isoformat()
        return {
            "schema_version": "1.0",
            "device_id": self.device_uid,
            "sequence": self.sequence_number,
            "timestamp": iso_now,
            "ppg": float(hr),
            "accel_x": 0.0,
            "accel_y": 0.0,
            "accel_z": float(g_force),
            "skin_temp": 36.6,
            "battery_pct": float(self.battery_pct),
            "heart_rate": float(hr),
            "spo2": float(spo2),
        }


class VirtualWardSimulator:
    def __init__(self, bed_count: int = 30):
        self.bands: List[VirtualWristband] = []
        for i in range(1, bed_count + 1):
            bed_id = f"BED-{i:02d}"
            pat_token = f"anon-PATIENT-{i:04d}"
            dev_uid = f"VIRT-NFC-{i:04X}"
            self.bands.append(VirtualWristband(bed_id, pat_token, dev_uid))

    async def pair_all_beds(self, client: httpx.AsyncClient) -> int:
        # Seed test beds and devices in DB if not exist
        try:
            from database import SessionLocal
            import models
            db = SessionLocal()
            for band in self.bands:
                if not db.query(models.Bed).filter(models.Bed.bed_no == band.bed_id).first():
                    db.add(models.Bed(bed_no=band.bed_id, ward_id="WARD-ICU"))
                if not db.query(models.Patient).filter(models.Patient.patient_token == band.patient_token).first():
                    db.add(models.Patient(patient_token=band.patient_token))
                if not db.query(models.Device).filter(models.Device.device_id == band.device_uid).first():
                    db.add(models.Device(device_id=band.device_uid, is_active=True))
            db.commit()
            db.close()
        except Exception as err:
            logger.debug("Local seed note: %s", err)

        paired_count = 0
        for band in self.bands:
            payload = {
                "bed_no": band.bed_id,
                "patient_token": band.patient_token,
                "device_id": band.device_uid,
                "placement_position": band.placement,
                "risk_level": "Low",
            }
            try:
                resp = await client.post(
                    f"{HUB_BASE_URL}/api/v1/pairing",
                    json=payload,
                    headers=HUB_AUTH_HEADER,
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    paired_count += 1
            except Exception as e:
                logger.debug("Pairing attempt error: %s", e)
        logger.info("Successfully paired %d / %d virtual beds with Ward Hub.", paired_count, len(self.bands))
        return paired_count

    async def stream_telemetry_loop(self, duration_seconds: int = 10):
        async with httpx.AsyncClient() as client:
            await self.pair_all_beds(client)
            start_time = time.time()
            ticks = 0

            while time.time() - start_time < duration_seconds:
                for band in self.bands:
                    packet = band.generate_packet()
                    try:
                        await client.post(
                            f"{HUB_BASE_URL}/api/v1/telemetry",
                            json=packet,
                            headers=HUB_AUTH_HEADER,
                            timeout=2.0,
                        )
                    except Exception:
                        pass
                ticks += 1
                await asyncio.sleep(1.0)
            logger.info("Virtual stream completed %d telemetry cycles across %d beds.", ticks, len(self.bands))


if __name__ == "__main__":
    sim = VirtualWardSimulator(30)
    asyncio.run(sim.stream_telemetry_loop(duration_seconds=3600))
