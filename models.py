from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.sql import func, text

from database import Base


class Patient(Base):
    __tablename__ = "patients"

    patient_token = Column(String, primary_key=True, index=True)


class Bed(Base):
    __tablename__ = "beds"

    bed_no = Column(String, primary_key=True, index=True)
    ward_id = Column(String, nullable=False, index=True, default="W04")
    availability_state = Column(String, nullable=False, default="AVAILABLE", index=True)
    availability_revision = Column(Integer, nullable=False, default=0)
    availability_updated_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class AdmissionPreparation(Base):
    __tablename__ = "admission_preparations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admission_id = Column(String, nullable=False, unique=True, index=True)
    bed_no = Column(String, ForeignKey("beds.bed_no"), nullable=False, index=True)
    patient_token = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="PREPARED", index=True)
    idempotency_key = Column(String, nullable=False, unique=True, index=True)
    source_console_id = Column(String, nullable=False, index=True)
    prepared_by = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    committed_session_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String, primary_key=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)


class DeviceCredential(Base):
    __tablename__ = "device_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=False, index=True)
    key_id = Column(String, nullable=False, unique=True, index=True)
    algorithm = Column(String, nullable=False, default="Ed25519")
    public_key_b64 = Column(String, nullable=False)
    certificate_fingerprint = Column(String, nullable=True)
    status = Column(String, nullable=False, default="ACTIVE", index=True)
    issued_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class NfcPointer(Base):
    __tablename__ = "nfc_pointers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nfc_uid = Column(String, nullable=False, unique=True, index=True)
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=False, index=True)
    key_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="ACTIVE", index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    revoked_at = Column(DateTime, nullable=True)


class WardSession(Base):
    __tablename__ = "ward_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, unique=True, index=True)
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=False, index=True)
    patient_token = Column(String, nullable=False, index=True)
    bed_no = Column(String, ForeignKey("beds.bed_no"), nullable=False, index=True)
    handover_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="ACTIVE", index=True)
    started_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    reset_pending_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class SessionCloseDigest(Base):
    __tablename__ = "session_close_digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, unique=True, index=True)
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=False, index=True)
    patient_token = Column(String, nullable=False, index=True)
    bed_no = Column(String, nullable=False, index=True)
    sample_count = Column(Integer, nullable=False)
    first_sequence = Column(Integer, nullable=True)
    last_sequence = Column(Integer, nullable=True)
    digest_hash = Column(String, nullable=False, unique=True, index=True)
    previous_digest_hash = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class Pairing(Base):
    __tablename__ = "pairings"
    __table_args__ = (
        Index(
            "uq_pairing_device_active",
            "device_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
        Index(
            "uq_pairing_bed_active",
            "bed_no",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_token = Column(String, ForeignKey("patients.patient_token"), nullable=False, index=True)
    bed_no = Column(String, ForeignKey("beds.bed_no"), nullable=False, index=True)
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=False, index=True)
    paired_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    unpaired_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)
    bed_no = Column(String, nullable=False, index=True)
    patient_token = Column(String, nullable=False, index=True)
    alert_level = Column(String, nullable=False)
    alert_type = Column(String, nullable=False)
    description = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    is_resolved = Column(Boolean, nullable=False, default=False, index=True)
    acknowledged = Column(Boolean, nullable=False, default=False, index=True)
    acknowledged_by = Column(String, nullable=True, index=True)
    acknowledged_at = Column(DateTime, nullable=True)


class TelemetryAggregate(Base):
    __tablename__ = "telemetry_aggregates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=False, index=True)
    patient_token = Column(String, nullable=False, index=True)
    bed_no = Column(String, nullable=False, index=True)
    sample_count = Column(Integer, nullable=False)
    ppg_avg = Column(Float, nullable=False)
    ppg_min = Column(Float, nullable=False)
    ppg_max = Column(Float, nullable=False)
    heart_rate_avg = Column(Float, nullable=True)
    heart_rate_min = Column(Float, nullable=True)
    heart_rate_max = Column(Float, nullable=True)
    spo2_avg = Column(Float, nullable=True)
    spo2_min = Column(Float, nullable=True)
    spo2_max = Column(Float, nullable=True)
    skin_temp_avg = Column(Float, nullable=False)
    skin_temp_min = Column(Float, nullable=True)
    skin_temp_max = Column(Float, nullable=True)
    battery_latest = Column(Float, nullable=False)
    max_accel_g = Column(Float, nullable=False)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class ForensicPackage(Base):
    __tablename__ = "forensic_packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=False, index=True)
    patient_token = Column(String, nullable=False, index=True)
    bed_no = Column(String, nullable=False, index=True)
    frozen_payload_json = Column(String, nullable=False)
    previous_hash = Column(String, nullable=False)
    block_hash = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class SyncAttempt(Base):
    __tablename__ = "sync_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, nullable=False, index=True)
    bundle_id = Column(String, nullable=False, index=True)
    status_code = Column(Integer, nullable=True)
    acknowledged = Column(Boolean, nullable=False, default=False, index=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class RoamingCommand(Base):
    __tablename__ = "roaming_commands"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command_id = Column(String, nullable=False, unique=True, index=True)
    idempotency_key = Column(String, nullable=False, unique=True, index=True)
    command_type = Column(String, nullable=False, index=True)
    actor_id = Column(String, nullable=False, index=True)
    tablet_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)
    alert_id = Column(Integer, nullable=True, index=True)
    admission_id = Column(String, nullable=True, index=True)
    expected_revision = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="PENDING", index=True)
    outcome_json = Column(String, nullable=True)
    error_code = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    processed_at = Column(DateTime, nullable=True, index=True)


class HandoverRecord(Base):
    __tablename__ = "handover_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, nullable=False, index=True)
    patient_token = Column(String, nullable=False, index=True)
    bed_no = Column(String, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    bundle_id = Column(String, nullable=False, unique=True, index=True)
    synced = Column(Boolean, nullable=False, default=False, index=True)
    purged_aggregate_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
