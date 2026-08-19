from __future__ import annotations

import base64
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from device_trust import canonicalize_telemetry, verify_device_signature
from edge_iot_adapters import TransportContext, build_adapter
from edge_runtime import EdgeTelemetryStore
from schemas import TelemetryPacket


DEVICE_ID = "device-serial-001"
NOW = datetime.now(timezone.utc)


def packet(sequence: int = 1) -> dict:
    return {
        "schema_version": "1.0",
        "device_id": DEVICE_ID,
        "sequence": sequence,
        "timestamp": NOW.isoformat(),
        "ppg": 0.82,
        "accel_x": 0.02,
        "accel_y": 0.01,
        "accel_z": 1.01,
        "skin_temp": 36.7,
        "battery_pct": 87.0,
        "heart_rate": 72.0,
        "spo2": 98.0,
    }


def envelope(sequence: int = 1, **extra: object) -> dict:
    value = {
        "packet": packet(sequence),
        "source_device_id": DEVICE_ID,
        "key_id": "key-serial-001",
        "signature_b64": "synthetic-signature-placeholder",
        "mapping_version": "serial-json-v1",
    }
    value.update(extra)
    return value


def context(transport: str, *, source_id: str = DEVICE_ID, require_signature: bool = True, max_frame_bytes: int = 16_384) -> TransportContext:
    return TransportContext(
        adapter_id=f"adapter-{transport}-001",
        transport=transport,  # type: ignore[arg-type]
        source_id=source_id,
        require_signature=require_signature,
        max_frame_bytes=max_frame_bytes,
    )


def run() -> None:
    for transport in ("mqtt", "websocket", "serial", "ble"):
        adapter = build_adapter(transport, f"adapter-{transport}-001")  # type: ignore[arg-type]
        frame: bytes | str = json.dumps(envelope()).encode("utf-8") if transport in {"serial", "ble"} else json.dumps(envelope())
        if transport == "serial":
            frame += b"\r\n"
        result = adapter.decode(frame, context(transport))
        assert result.normalized
        assert result.packet is not None
        assert result.packet.model_dump()["schema_version"] == "1.0"
        assert result.details["trust_state"] == "PENDING_FIXED_HUB_VERIFY"
        assert "patient_token" not in result.redacted_evidence()
    print("[P2-002] MQTT/WebSocket/Serial/BLE frames normalize to TelemetryPacket v1: PASSED")

    serial = build_adapter("serial", "adapter-serial-001")
    missing_signature = serial.decode({"packet": packet(), "source_device_id": DEVICE_ID}, context("serial"))
    assert missing_signature.failure_class == "signature_missing"
    print("[P2-002] Enforce-mode adapter rejects missing signature envelope: PASSED")

    unknown_field = serial.decode({**envelope(), "unexpected": "must-not-forward"}, context("serial"))
    assert unknown_field.failure_class == "unknown_outer_field"
    print("[P2-002] Unknown outer fields are rejected: PASSED")

    pii_frame = envelope()
    pii_frame["packet"] = {**packet(), "patient_token": "opaque-token-must-not-enter-adapter"}
    pii = serial.decode(pii_frame, context("serial"))
    assert pii.failure_class == "pii_or_secret_field_detected"
    print("[P2-002] PII-bearing packet is rejected before normalization: PASSED")

    command_frame = envelope()
    command_frame["command_type"] = "RESET_CONFIRM"
    command = serial.decode(command_frame, context("serial"))
    assert command.failure_class == "command_field_detected"
    print("[P2-002] Workflow command field cannot enter telemetry adapter: PASSED")

    mismatch = serial.decode(envelope(), context("serial", source_id="different-device"))
    assert mismatch.failure_class == "transport_identity_mismatch"
    print("[P2-002] Transport source identity mismatch is rejected: PASSED")

    oversized = serial.decode(json.dumps(envelope()).encode("utf-8"), context("serial", max_frame_bytes=16))
    assert oversized.failure_class == "frame_too_large"
    print("[P2-002] Bounded frame size rejects oversized input: PASSED")

    wrong_context = serial.decode(envelope(), context("mqtt"))
    assert wrong_context.failure_class == "transport_context_mismatch"
    print("[P2-002] Adapter/transport context mismatch is rejected: PASSED")

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes_raw()
    packet_model = TelemetryPacket.model_validate(packet())
    signature = private_key.sign(canonicalize_telemetry(packet_model.model_dump()))
    public_b64 = base64.urlsafe_b64encode(public_key).decode().rstrip("=")
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    verified = verify_device_signature(
        packet_model.model_dump(),
        public_key_b64=public_b64,
        algorithm="Ed25519",
        signature_b64=signature_b64,
        now=NOW,
        timestamp_skew_seconds=30,
        status="ACTIVE",
    )
    assert verified.valid is True
    print("[P2-002] Normalized packet remains verifiable by Device Trust canonical signature: PASSED")

    with tempfile.TemporaryDirectory() as temp_dir:
        store = EdgeTelemetryStore(max_samples=4, state_path=Path(temp_dir) / "state.json", checkpoint_every=1)
        first = store.append(DEVICE_ID, {"sequence": 1, "timestamp": NOW, "accel_x": 0.0}, 1)
        duplicate = store.append(DEVICE_ID, {"sequence": 1, "timestamp": NOW, "accel_x": 0.0}, 1)
        older = store.append(DEVICE_ID, {"sequence": 0, "timestamp": NOW, "accel_x": 0.0}, 0)
        newer = store.append(DEVICE_ID, {"sequence": 2, "timestamp": NOW, "accel_x": 0.0}, 2)
        assert first.accepted and newer.accepted
        assert duplicate.reason == "duplicate_or_out_of_order_sequence"
        assert older.reason == "duplicate_or_out_of_order_sequence"
    print("[P2-002] Duplicate and out-of-order replay remain rejected by EdgeTelemetryStore: PASSED")

    pilot_gate = {
        "selected_transport": "serial",
        "contract_translation": True,
        "trust_envelope": True,
        "malformed_input": True,
        "pii_rejection": True,
        "command_rejection": True,
        "replay_guard": True,
        "bounded_frame": True,
        "hardware_evidence": "UNVERIFIED",
    }
    boolean_gates = [key for key, value in pilot_gate.items() if isinstance(value, bool)]
    assert boolean_gates and all(pilot_gate[key] is True for key in boolean_gates)
    assert pilot_gate["selected_transport"] == "serial"
    assert pilot_gate["hardware_evidence"] == "UNVERIFIED"
    print("[P2-002] One-transport software pilot gate is satisfied; hardware evidence remains UNVERIFIED: PASSED")
    print("P2_EDGE_IOT_ADAPTER_TESTS_PASSED")


if __name__ == "__main__":
    run()
