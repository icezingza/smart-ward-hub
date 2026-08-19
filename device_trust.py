from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import binascii
import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


SUPPORTED_ALGORITHM = "Ed25519"


@dataclass(frozen=True)
class DeviceTrustVerification:
    valid: bool
    reason: str
    fingerprint: str | None = None


def _canonical_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    return value


def canonicalize_telemetry(packet: dict[str, Any]) -> bytes:
    """Return the one canonical byte representation signed by a device."""
    normalized = _canonical_value(dict(packet))
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def public_key_fingerprint(public_key_b64: str) -> str:
    raw = _decode_b64(public_key_b64, expected_length=32)
    return hashlib.sha256(raw).hexdigest()


def _decode_b64(value: str, *, expected_length: int | None = None) -> bytes:
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError("invalid base64 value")
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.urlsafe_b64decode(value + padding)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid base64 value") from exc
    if expected_length is not None and len(decoded) != expected_length:
        raise ValueError("unexpected decoded length")
    return decoded


def verify_device_signature(
    packet: dict[str, Any],
    *,
    public_key_b64: str,
    algorithm: str,
    signature_b64: str,
    now: datetime | None = None,
    timestamp_skew_seconds: int = 30,
    expires_at: datetime | None = None,
    status: str = "ACTIVE",
) -> DeviceTrustVerification:
    if algorithm != SUPPORTED_ALGORITHM:
        return DeviceTrustVerification(False, "unsupported_algorithm")
    if status != "ACTIVE":
        return DeviceTrustVerification(False, f"credential_{status.lower()}")

    current = now or datetime.now(timezone.utc)
    packet_timestamp = packet.get("timestamp")
    if not isinstance(packet_timestamp, datetime):
        return DeviceTrustVerification(False, "invalid_timestamp")
    timestamp_utc = packet_timestamp if packet_timestamp.tzinfo else packet_timestamp.replace(tzinfo=timezone.utc)
    if abs((current - timestamp_utc.astimezone(timezone.utc)).total_seconds()) > timestamp_skew_seconds:
        return DeviceTrustVerification(False, "timestamp_outside_allowed_skew")
    if expires_at is not None:
        expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        if current >= expiry.astimezone(timezone.utc):
            return DeviceTrustVerification(False, "credential_expired")

    try:
        public_key_raw = _decode_b64(public_key_b64, expected_length=32)
        signature_raw = _decode_b64(signature_b64, expected_length=64)
        fingerprint = hashlib.sha256(public_key_raw).hexdigest()
        Ed25519PublicKey.from_public_bytes(public_key_raw).verify(
            signature_raw,
            canonicalize_telemetry(packet),
        )
    except (ValueError, InvalidSignature, TypeError):
        return DeviceTrustVerification(False, "signature_invalid")
    return DeviceTrustVerification(True, "verified", fingerprint)
