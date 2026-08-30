from datetime import datetime, timezone
from typing import Any, Literal, Optional
import re

from pydantic import BaseModel, Field, field_validator, model_validator


DEVICE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"


class PairingRequest(BaseModel):
    patient_token: str = Field(..., min_length=16, max_length=128, description="Pseudonymized HIS patient reference")
    bed_no: str = Field(..., min_length=1, max_length=32, description="Ward bed number")
    device_id: str = Field(..., min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN, description="Registered wristband identifier")
    risk_level: str = Field(default="Low", pattern="^(High|Medium|Low)$")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("patient_token", "bed_no", "device_id")
    @classmethod
    def strip_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("identifier must not be blank")
        return value

    @field_validator("patient_token")
    @classmethod
    def require_opaque_patient_token(cls, value: str) -> str:
        if (
            not re.fullmatch(r"[A-Za-z0-9._~-]{16,128}", value)
            or re.match(r"^(HN|AN)([-_:]|$)", value, flags=re.IGNORECASE)
        ):
            raise ValueError("patient_token must be an opaque token; raw HN/AN formats are not accepted")
        return value


class UnbindRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN, description="Wristband identifier")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("device_id")
    @classmethod
    def strip_device_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("device_id must not be blank")
        return value


class BaseResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict[str, Any]] = None


class TelemetryPacket(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    device_id: str = Field(..., min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN)
    sequence: int = Field(..., ge=0, description="Monotonic per-device packet sequence")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ppg: float = Field(..., ge=0)
    accel_x: float
    accel_y: float
    accel_z: float
    skin_temp: float = Field(..., ge=0, le=100)
    battery_pct: float = Field(..., ge=0, le=100)
    heart_rate: float | None = Field(default=None, ge=0, le=300)
    spo2: float | None = Field(default=None, ge=0, le=100)

    @field_validator("device_id")
    @classmethod
    def normalize_device_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("device_id must not be blank")
        return value


class DeviceTrustEnrollmentRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN)
    key_id: str = Field(..., min_length=1, max_length=128)
    algorithm: Literal["Ed25519"] = "Ed25519"
    public_key_b64: str = Field(..., min_length=40, max_length=128)
    certificate_fingerprint: str | None = Field(default=None, min_length=16, max_length=128)
    expires_at: datetime | None = None

    @field_validator("device_id", "key_id", "public_key_b64")
    @classmethod
    def strip_trusted_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("trusted identifier must not be blank")
        return value


class DeviceTrustLifecycleRequest(BaseModel):
    key_id: str = Field(..., min_length=1, max_length=128)
    status: Literal["ACTIVE", "SUSPENDED", "REVOKED"]


class NfcPointerEnrollmentRequest(BaseModel):
    nfc_uid: str = Field(..., min_length=4, max_length=128)
    device_id: str = Field(..., min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN)
    key_id: str | None = Field(default=None, max_length=128)

    @field_validator("nfc_uid", "device_id", "key_id")
    @classmethod
    def strip_pointer_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("pointer identifier must not be blank")
        return value


class NfcPointerResolveRequest(BaseModel):
    nfc_uid: str = Field(..., min_length=4, max_length=128)


class RoamingCommandRequest(BaseModel):
    command_type: Literal["ACK_ALERT", "NOTE", "RESET_REQUEST", "RESET_CONFIRM", "ADMISSION_TASK_ACK"]
    command_id: str = Field(..., min_length=8, max_length=128)
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    tablet_id: str = Field(..., min_length=1, max_length=64)
    expected_revision: int = Field(..., ge=0)
    session_id: str | None = Field(default=None, max_length=128)
    alert_id: int | None = Field(default=None, ge=1)
    admission_id: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=512)

    @field_validator("command_id", "idempotency_key", "tablet_id", "session_id", "admission_id")
    @classmethod
    def strip_roaming_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("roaming identifier must not be blank")
        return value


class BedAvailabilityStateRequest(BaseModel):
    state: Literal["AVAILABLE", "CLEANING", "BLOCKED", "MAINTENANCE"]
    reason: str | None = Field(default=None, max_length=256)


class AdmissionPreparationRequest(BaseModel):
    patient_token: str = Field(..., min_length=16, max_length=128)
    bed_no: str = Field(..., min_length=1, max_length=32)
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    source_console_id: str = Field(..., min_length=1, max_length=64)
    expires_in_seconds: int = Field(default=300, ge=30, le=3600)

    @field_validator("patient_token", "bed_no", "idempotency_key", "source_console_id")
    @classmethod
    def strip_admission_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("admission identifier must not be blank")
        return value

    @field_validator("patient_token")
    @classmethod
    def require_opaque_admission_token(cls, value: str) -> str:
        if (
            not re.fullmatch(r"[A-Za-z0-9._~-]{16,128}", value)
            or re.match(r"^(HN|AN)([-_:]|$)", value, flags=re.IGNORECASE)
        ):
            raise ValueError("patient_token must be an opaque token; raw HN/AN formats are not accepted")
        return value


class HotSwapRequest(BaseModel):
    new_device_id: str = Field(..., min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN)
    new_key_id: str | None = Field(default=None, max_length=128)
    handover_id: str = Field(..., min_length=8, max_length=128)


class ResetConfirmRequest(BaseModel):
    confirmation_code: Literal["RESET"]


class DischargeRequest(BaseModel):
    handover_id: str = Field(..., min_length=8, max_length=128)


class TelemetryAggregateResponse(BaseModel):
    device_id: str
    patient_token: str
    bed_no: str
    sample_count: int
    ppg_avg: float
    ppg_min: float
    ppg_max: float
    heart_rate_avg: float | None = None
    heart_rate_min: float | None = None
    heart_rate_max: float | None = None
    spo2_avg: float | None = None
    spo2_min: float | None = None
    spo2_max: float | None = None
    skin_temp_avg: float
    skin_temp_min: float | None = None
    skin_temp_max: float | None = None
    battery_latest: float
    max_accel_g: float
    window_start: str
    window_end: str


class HandoverRequest(BaseModel):
    start_time: datetime
    end_time: datetime

    @field_validator("end_time")
    @classmethod
    def validate_window(cls, value: datetime, info):
        start_time = info.data.get("start_time")
        if start_time is not None and value <= start_time:
            raise ValueError("end_time must be later than start_time")
        return value


class HandoverSyncRequest(BaseModel):
    acknowledged: bool = False
    status_code: int = Field(..., ge=100, le=599)
    error_message: str | None = Field(default=None, max_length=512)
    acknowledged_bundle_id: str | None = Field(default=None, min_length=1, max_length=128)
    acknowledgment_id: str | None = Field(default=None, min_length=1, max_length=128)
    receiving_system: str | None = Field(default=None, min_length=1, max_length=128)
    server_time: datetime | None = None
    accepted_version: str | None = Field(default=None, min_length=1, max_length=64)
    accepted_profile: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_acknowledgment_contract(self):
        if not self.acknowledged:
            return self
        if self.status_code != 200:
            raise ValueError("acknowledged responses must use status_code 200")
        required = {
            "acknowledged_bundle_id": self.acknowledged_bundle_id,
            "acknowledgment_id": self.acknowledgment_id,
            "receiving_system": self.receiving_system,
            "server_time": self.server_time,
            "accepted_version": self.accepted_version,
            "accepted_profile": self.accepted_profile,
        }
        missing = [name for name, value in required.items() if value in (None, "")]
        if missing:
            raise ValueError(
                "structured acknowledgment required: " + ", ".join(sorted(missing))
            )
        if self.server_time is not None and self.server_time.tzinfo is None:
            raise ValueError("server_time must include an explicit timezone")
        return self


class HandoverResponse(BaseModel):
    bundle_id: str
    device_id: str
    patient_token: str
    bed_no: str
    start_time: str
    end_time: str
    clinical_metrics: dict[str, Any]
    alert_count: int
    fhir_bundle: dict[str, Any]
    sync_status: str
    aggregate_count: int


class HisSyncPurgeRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN)
    his_http_status: int = Field(default=200, description="HTTP status code returned by HIS endpoint")
    his_response_payload: Optional[dict[str, Any]] = Field(default_factory=dict, description="Payload returned by HIS endpoint")
