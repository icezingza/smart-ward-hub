from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

try:
    from pydantic import ValidationError
    from schemas import TelemetryPacket
except ModuleNotFoundError:
    from pydantic import ValidationError
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from schemas import TelemetryPacket


TransportName = Literal["mqtt", "websocket", "serial", "ble"]
AdapterStatus = Literal["NORMALIZED", "REJECTED", "RETRYABLE_FAILURE"]

PACKET_FIELDS = set(TelemetryPacket.model_fields)
OUTER_FIELDS = {"packet", "key_id", "signature_b64", "source_device_id", "mapping_version", "gateway_attested"}
SENSITIVE_KEYS = {"name", "patient_id", "patient_token", "patient_name", "hn", "an", "hospital_number", "private_key", "bearer_token"}
COMMAND_KEYS = {"command", "command_type", "reset_confirm", "discharge", "purge", "resolve_alert"}


@dataclass(frozen=True)
class TransportContext:
    adapter_id: str
    transport: TransportName
    source_id: str
    require_signature: bool = True
    max_frame_bytes: int = 16_384
    gateway_attested: bool = False


@dataclass(frozen=True)
class AdapterResult:
    status: AdapterStatus
    adapter_id: str
    transport: TransportName
    device_id: str | None = None
    sequence: int | None = None
    packet: TelemetryPacket | None = None
    key_id: str | None = None
    signature_b64: str | None = None
    failure_class: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized(self) -> bool:
        return self.status == "NORMALIZED" and self.packet is not None

    def redacted_evidence(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "adapter_id": self.adapter_id,
            "transport": self.transport,
            "device_id": self.device_id,
            "sequence": self.sequence,
            "key_id": self.key_id,
            "failure_class": self.failure_class,
            "details": {key: value for key, value in self.details.items() if key not in SENSITIVE_KEYS},
        }


class EdgeIoTAdapter:
    transport: TransportName
    frame_limit: int = 16_384

    def __init__(self, adapter_id: str) -> None:
        self.adapter_id = adapter_id

    def decode(self, frame: bytes | str | dict[str, Any], context: TransportContext) -> AdapterResult:
        raise NotImplementedError

    def health(self) -> dict[str, Any]:
        return {"adapter_id": self.adapter_id, "transport": self.transport, "state": "READY"}

    def _rejected(self, context: TransportContext, failure_class: str, *, device_id: str | None = None, sequence: int | None = None, details: dict[str, Any] | None = None) -> AdapterResult:
        return AdapterResult(
            status="REJECTED",
            adapter_id=self.adapter_id,
            transport=context.transport,
            device_id=device_id,
            sequence=sequence,
            failure_class=failure_class,
            details=details or {},
        )

    def _decode_json(self, frame: bytes | str | dict[str, Any], context: TransportContext) -> dict[str, Any] | AdapterResult:
        if isinstance(frame, dict):
            raw = frame
        else:
            if isinstance(frame, str):
                encoded = frame.encode("utf-8")
            elif isinstance(frame, bytes):
                encoded = frame
            else:
                return self._rejected(context, "invalid_frame_type")
            if len(encoded) > min(self.frame_limit, context.max_frame_bytes):
                return self._rejected(context, "frame_too_large")
            try:
                text = encoded.decode("utf-8").strip()
            except UnicodeDecodeError:
                return self._rejected(context, "malformed_encoding")
            if not text:
                return self._rejected(context, "empty_frame")
            try:
                raw = json.loads(text)
            except json.JSONDecodeError:
                return self._rejected(context, "invalid_json_or_frame")
        if not isinstance(raw, dict):
            return self._rejected(context, "frame_must_be_object")
        return raw

    def _validate_envelope(self, raw: dict[str, Any], context: TransportContext) -> tuple[dict[str, Any], dict[str, Any]] | AdapterResult:
        unknown_outer = set(raw) - OUTER_FIELDS
        sensitive = {key for key in raw if key.lower() in SENSITIVE_KEYS}
        commands = {key for key in raw if key.lower() in COMMAND_KEYS}
        if sensitive:
            return self._rejected(context, "pii_or_secret_field_detected", details={"field_count": len(sensitive)})
        if commands:
            return self._rejected(context, "command_field_detected", details={"field_count": len(commands)})
        if unknown_outer:
            return self._rejected(context, "unknown_outer_field", details={"field_count": len(unknown_outer)})
        packet_raw = raw.get("packet")
        if not isinstance(packet_raw, dict):
            return self._rejected(context, "packet_object_required")
        unknown_packet = set(packet_raw) - PACKET_FIELDS
        sensitive_packet = {key for key in packet_raw if key.lower() in SENSITIVE_KEYS}
        commands_packet = {key for key in packet_raw if key.lower() in COMMAND_KEYS}
        if sensitive_packet:
            return self._rejected(context, "pii_or_secret_field_detected", details={"field_count": len(sensitive_packet)})
        if commands_packet:
            return self._rejected(context, "command_field_detected", details={"field_count": len(commands_packet)})
        if unknown_packet:
            return self._rejected(context, "unknown_packet_field", details={"field_count": len(unknown_packet)})
        key_id = raw.get("key_id")
        signature_b64 = raw.get("signature_b64")
        if context.require_signature and (not isinstance(key_id, str) or not key_id.strip() or not isinstance(signature_b64, str) or not signature_b64.strip()):
            return self._rejected(context, "signature_missing")
        source_device_id = raw.get("source_device_id")
        packet_device_id = packet_raw.get("device_id")
        if source_device_id is not None and source_device_id != packet_device_id:
            return self._rejected(context, "source_device_mismatch", device_id=str(packet_device_id) if packet_device_id else None)
        metadata = {
            "key_id": key_id,
            "signature_b64": signature_b64,
            "mapping_version": raw.get("mapping_version"),
            "gateway_attested": bool(raw.get("gateway_attested", context.gateway_attested)),
        }
        return packet_raw, metadata

    def _normalize(self, raw: dict[str, Any], context: TransportContext) -> AdapterResult:
        validated = self._validate_envelope(raw, context)
        if isinstance(validated, AdapterResult):
            return validated
        packet_raw, metadata = validated
        try:
            packet = TelemetryPacket.model_validate(packet_raw)
        except ValidationError:
            return self._rejected(context, "schema_invalid", device_id=str(packet_raw.get("device_id")) if packet_raw.get("device_id") else None)
        if packet.device_id != context.source_id and context.source_id not in {"gateway", "unknown"}:
            return self._rejected(context, "transport_identity_mismatch", device_id=packet.device_id, sequence=packet.sequence)
        return AdapterResult(
            status="NORMALIZED",
            adapter_id=self.adapter_id,
            transport=context.transport,
            device_id=packet.device_id,
            sequence=packet.sequence,
            packet=packet,
            key_id=metadata["key_id"],
            signature_b64=metadata["signature_b64"],
            details={
                "trust_state": "PENDING_FIXED_HUB_VERIFY",
                "mapping_version": metadata["mapping_version"],
                "gateway_attested": metadata["gateway_attested"],
            },
        )

    def decode(self, frame: bytes | str | dict[str, Any], context: TransportContext) -> AdapterResult:
        if context.transport != self.transport:
            return self._rejected(context, "transport_context_mismatch")
        raw = self._decode_json(frame, context)
        if isinstance(raw, AdapterResult):
            return raw
        return self._normalize(raw, context)


class MqttTelemetryAdapter(EdgeIoTAdapter):
    transport: TransportName = "mqtt"
    frame_limit = 16_384


class WebSocketTelemetryAdapter(EdgeIoTAdapter):
    transport: TransportName = "websocket"
    frame_limit = 16_384


class SerialTelemetryAdapter(EdgeIoTAdapter):
    transport: TransportName = "serial"
    frame_limit = 4_096

    def decode(self, frame: bytes | str | dict[str, Any], context: TransportContext) -> AdapterResult:
        if isinstance(frame, bytes):
            frame = frame.rstrip(b"\r\n")
        elif isinstance(frame, str):
            frame = frame.rstrip("\r\n")
        return super().decode(frame, context)


class BleTelemetryAdapter(EdgeIoTAdapter):
    transport: TransportName = "ble"
    frame_limit = 512


ADAPTER_TYPES = {
    "mqtt": MqttTelemetryAdapter,
    "websocket": WebSocketTelemetryAdapter,
    "serial": SerialTelemetryAdapter,
    "ble": BleTelemetryAdapter,
}


def build_adapter(transport: TransportName, adapter_id: str) -> EdgeIoTAdapter:
    try:
        return ADAPTER_TYPES[transport](adapter_id)
    except KeyError as exc:
        raise ValueError(f"unsupported transport: {transport}") from exc
