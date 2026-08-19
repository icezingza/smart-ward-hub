from __future__ import annotations

import json

from edge_iot_adapters import TransportContext, build_adapter
from serial_framing import ETX, FRAME_VERSION, STX, SerialFrameCodec


DEVICE_ID = "device-serial-bench-001"


def envelope(sequence: int = 1) -> dict:
    return {
        "packet": {
            "schema_version": "1.0",
            "device_id": DEVICE_ID,
            "sequence": sequence,
            "timestamp": "2026-08-20T00:00:00Z",
            "ppg": 0.82,
            "accel_x": 0.02,
            "accel_y": 0.01,
            "accel_z": 1.01,
            "skin_temp": 36.7,
            "battery_pct": 87.0,
            "heart_rate": 72.0,
            "spo2": 98.0,
        },
        "source_device_id": DEVICE_ID,
        "key_id": "key-serial-bench-001",
        "signature_b64": "synthetic-signature-placeholder",
        "mapping_version": "serial-json-v1",
    }


def payload(sequence: int = 1) -> bytes:
    return json.dumps(envelope(sequence), separators=(",", ":")).encode("utf-8")


def frame(sequence: int = 1) -> bytes:
    return SerialFrameCodec.encode(payload(sequence), max_payload=4096)


def frame_events(codec: SerialFrameCodec, data: bytes, chunk_sizes: list[int]) -> list:
    events = []
    offset = 0
    for size in chunk_sizes:
        events.extend(codec.feed(data[offset:offset + size]))
        offset += size
    if offset < len(data):
        events.extend(codec.feed(data[offset:]))
    return events


def run() -> None:
    encoded = frame()
    assert encoded[0] == STX and encoded[-1] == ETX
    decoded = SerialFrameCodec()
    events = decoded.feed(encoded)
    assert [event.kind for event in events] == ["frame"]
    assert events[0].payload == payload()
    print("[Serial] Full frame encode/decode with CRC32: PASSED")

    partial = SerialFrameCodec()
    one_byte_events = frame_events(partial, encoded, [1] * len(encoded))
    assert [event.kind for event in one_byte_events] == ["frame"]
    assert one_byte_events[0].payload == payload()
    assert partial.buffered_bytes == 0
    print("[Serial] One-byte-at-a-time partial reads reconstruct one frame: PASSED")

    split = SerialFrameCodec()
    split_events = frame_events(split, encoded, [1, 2, 1, 3, 5, 8, 13])
    assert [event.kind for event in split_events] == ["frame"]
    print("[Serial] Irregular partial-read boundaries reconstruct one frame: PASSED")

    concat = SerialFrameCodec()
    concatenated_events = concat.feed(frame(1) + frame(2))
    assert [event.kind for event in concatenated_events] == ["frame", "frame"]
    assert concatenated_events[0].payload == payload(1)
    assert concatenated_events[1].payload == payload(2)
    print("[Serial] Back-to-back frames are separated without loss: PASSED")

    truncated = SerialFrameCodec()
    truncated_events = truncated.feed(encoded[:-2])
    assert truncated_events == []
    assert truncated.buffered_bytes == len(encoded) - 2
    print("[Serial] Truncated frame waits for completion without emitting data: PASSED")

    corrupt = bytearray(encoded)
    corrupt[8] ^= 0x01
    crc_events = SerialFrameCodec().feed(bytes(corrupt))
    assert any(event.kind == "crc_mismatch" for event in crc_events)
    assert not any(event.kind == "frame" for event in crc_events)
    print("[Serial] CRC mutation is rejected: PASSED")

    bad_terminator = bytearray(encoded)
    bad_terminator[-1] = 0x04
    terminator_events = SerialFrameCodec().feed(bytes(bad_terminator))
    assert any(event.kind == "bad_terminator" for event in terminator_events)
    print("[Serial] Invalid terminator is rejected: PASSED")

    oversize_header = bytes([STX, FRAME_VERSION, 0]) + (4097).to_bytes(2, "big")
    oversize_events = SerialFrameCodec(max_payload=4096).feed(oversize_header)
    assert any(event.kind == "payload_too_large" for event in oversize_events)
    print("[Serial] Oversized payload declaration is rejected before allocation: PASSED")

    noisy = SerialFrameCodec()
    noisy_events = noisy.feed(b"noise-before" + encoded)
    assert [event.kind for event in noisy_events] == ["noise_discarded", "frame"]
    print("[Serial] Leading noise is discarded and parser resynchronizes: PASSED")

    overflow = SerialFrameCodec(max_payload=32, max_buffer=40)
    overflow_events = overflow.feed(b"\x99" * 100)
    assert any(event.kind == "buffer_overflow" for event in overflow_events)
    assert overflow.buffered_bytes <= overflow.max_buffer
    print("[Serial] Partial-read buffer remains bounded under overflow: PASSED")

    reconnect = SerialFrameCodec()
    reconnect.feed(encoded[:-3])
    reconnect.reset()
    reconnect_events = reconnect.feed(frame(7))
    assert [event.kind for event in reconnect_events] == ["frame"]
    assert reconnect_events[0].payload == payload(7)
    print("[Serial] Reset after disconnect prevents stale partial-frame contamination: PASSED")

    adapter = build_adapter("serial", "adapter-serial-bench-001")
    adapter_context = TransportContext(
        adapter_id="adapter-serial-bench-001",
        transport="serial",
        source_id=DEVICE_ID,
        require_signature=True,
        max_frame_bytes=4096,
    )
    parsed_payload = SerialFrameCodec().feed(encoded)[0].payload
    assert parsed_payload is not None
    adapter_result = adapter.decode(parsed_payload, adapter_context)
    assert adapter_result.normalized
    assert adapter_result.packet is not None
    assert adapter_result.packet.sequence == 1
    print("[Serial] Valid framed payload reaches TelemetryPacket v1 adapter boundary: PASSED")

    malformed_json = SerialFrameCodec.encode(b"{not-json", max_payload=4096)
    malformed_payload = SerialFrameCodec().feed(malformed_json)[0].payload
    assert malformed_payload is not None
    malformed_result = adapter.decode(malformed_payload, adapter_context)
    assert malformed_result.failure_class == "invalid_json_or_frame"
    print("[Serial] CRC-valid but malformed JSON is rejected by adapter: PASSED")

    print("SERIAL_FRAMING_PARTIAL_READ_TESTS_PASSED")


if __name__ == "__main__":
    run()
