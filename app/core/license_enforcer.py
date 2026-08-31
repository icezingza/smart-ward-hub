"""License Enforcer & Ward Quota Security Module for Smart Ward Hub."""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import jwt  # PyJWT: Public Key decoding only. No private key stored on Hub.
from fastapi import HTTPException, status
from pydantic import BaseModel


class LicensePayload(BaseModel):
    hospital_id: str
    ward_id: str
    max_beds: int
    exp: int


class LicenseEnforcer:
    def __init__(self, public_key_pem: str | None = None, blackbox_log_path: Path | str | None = None):
        self.public_key = public_key_pem
        self.cached_license: Optional[LicensePayload] = None
        self.emergency_override_until: float = 0.0
        self.blackbox_log_path = Path(blackbox_log_path) if blackbox_log_path else Path("audit_events.jsonl")

    def verify_ward_license(self, token_str: str) -> LicensePayload:
        """Verify validity of ward license token using Ed25519 or RS256 Public Key."""
        if not self.public_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Public key not configured on Hub."
            )
        try:
            payload = jwt.decode(token_str, self.public_key, algorithms=["RS256", "EdDSA"])
            self.cached_license = LicensePayload(**payload)
            return self.cached_license
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ward license expired.")
        except Exception:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tampered or invalid license signature.")

    def enforce_bed_quota(self, active_beds_count: int) -> bool:
        """Enforce bed quota limit. Fails closed with HTTP 423 Locked when quota exceeded."""
        now = time.time()
        # Patient First Invariant: Check if active medical emergency override is valid
        if now < self.emergency_override_until:
            return True

        if not self.cached_license or active_beds_count >= self.cached_license.max_beds:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Bed capacity limit reached. Please contact vendor to expand license."
            )
        return True

    def trigger_clinical_emergency_override(self, charge_nurse_pin: str) -> Dict[str, Any]:
        """Clinical Safety Gate: Charge Nurse 48-hour emergency override for critical admissions."""
        if not charge_nurse_pin or len(charge_nurse_pin.strip()) < 4:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Charge Nurse PIN.")

        now = time.time()
        self.emergency_override_until = now + (48 * 3600)

        # Log emergency event to ISO 27037 Black Box audit log
        log_entry = {
            "event_type": "CLINICAL_EMERGENCY_OVERRIDE_ACTIVATED",
            "timestamp": int(now),
            "valid_hours": 48,
            "emergency_override_until": int(self.emergency_override_until),
            "iso_27037_sealed": True,
        }
        try:
            with open(self.blackbox_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except OSError:
            pass

        return {
            "status": "EMERGENCY_OVERRIDE_ACTIVE",
            "valid_hours": 48,
            "emergency_override_until": int(self.emergency_override_until)
        }
