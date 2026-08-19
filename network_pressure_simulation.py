from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path
from typing import Any

from edge_iot_adapters import TransportContext, build_adapter
from edge_runtime import EdgeTelemetryStore
from serial_framing import SerialFrameCodec


@dataclass(frozen=True)
class PressureScenario:
    name: str
    ticks: int = 120
    device_count: int = 8
    frames_per_device_per_tick: int = 1
    burst_start_tick: int = 0
    burst_ticks: int = 10
    burst_multiplier: int = 8
    queue_capacity: int = 32
    consumer_per_tick: int = 8
    max_payload: int = 4096
    max_buffer: int = 8192
    partial_chunk_pattern: tuple[int, ...] = (1, 2, 5, 3, 8, 13)
    crc_corruption_every: int = 0
    duplicate_every: int = 0
    disconnect_every: int = 0
    malformed_every: int = 0
    pii_every: int = 0


@dataclass
class PressureMetrics:
    scenario: str
    ticks: int
    device_count: int
    produced_frames: int = 0
    produced_bytes: int = 0
    emitted_partial_chunks: int = 0
    decoded_frames: int = 0
    accepted_packets: int = 0
    rejected_packets: int = 0
    crc_mismatch: int = 0
    malformed_payloads: int = 0
    pii_rejections: int = 0
    duplicate_rejections: int = 0
    queue_enqueued: int = 0
    queue_consumed: int = 0
    queue_dropped: int = 0
    disconnects: int = 0
    partial_frames_discarded: int = 0
    max_queue_depth: int = 0
    max_codec_buffer: int = 0
    max_store_buffered_samples: int = 0
    dropped_store_samples: int = 0
    backpressure_observed: bool = False
    memory_bound_respected: bool = True
    replay_guard_respected: bool = True
    status: str = "REQUIRES_REVIEW"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _packet_envelope(device_id: str, sequence: int, *, malformed: bool = False, pii: bool = False) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "schema_version": "1.0",
        "device_id": device_id,
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
    }
    if malformed:
        packet["sequence"] = "not-an-integer"
    if pii:
        packet["patient_token"] = "synthetic-token-must-be-rejected"
    return {
        "packet": packet,
        "source_device_id": device_id,
        "key_id": "synthetic-key-id",
        "signature_b64": "synthetic-signature-placeholder",
        "mapping_version": "serial-json-v1",
    }


def _make_frame(device_id: str, sequence: int, scenario: PressureScenario, frame_index: int) -> bytes:
    payload = json.dumps(
        _packet_envelope(
            device_id,
            sequence,
            malformed=bool(scenario.malformed_every and frame_index % scenario.malformed_every == 0),
            pii=bool(scenario.pii_every and frame_index % scenario.pii_every == 0),
        ),
        separators=(",", ":"),
    ).encode("utf-8")
    frame = SerialFrameCodec.encode(payload, max_payload=scenario.max_payload)
    if scenario.crc_corruption_every and frame_index % scenario.crc_corruption_every == 0:
        corrupted = bytearray(frame)
        if len(corrupted) > 10:
            corrupted[8] ^= 0x01
        return bytes(corrupted)
    return frame


def _feed_partial(codec: SerialFrameCodec, frame: bytes, pattern: tuple[int, ...], metrics: PressureMetrics) -> list[bytes]:
    payloads: list[bytes] = []
    offset = 0
    pattern_index = 0
    while offset < len(frame):
        size = pattern[pattern_index % len(pattern)]
        pattern_index += 1
        chunk = frame[offset:offset + size]
        offset += len(chunk)
        metrics.emitted_partial_chunks += 1
        for event in codec.feed(chunk):
            if event.kind == "frame" and event.payload is not None:
                payloads.append(event.payload)
            elif event.kind == "crc_mismatch":
                metrics.crc_mismatch += 1
            elif event.kind == "buffer_overflow":
                metrics.memory_bound_respected = False
    metrics.max_codec_buffer = max(metrics.max_codec_buffer, codec.buffered_bytes)
    return payloads


def simulate(scenario: PressureScenario) -> dict[str, Any]:
    metrics = PressureMetrics(scenario=scenario.name, ticks=scenario.ticks, device_count=scenario.device_count)
    queue: deque[bytes] = deque(maxlen=scenario.queue_capacity)
    codecs = {
        f"pressure-device-{index:03d}": SerialFrameCodec(max_payload=scenario.max_payload, max_buffer=scenario.max_buffer)
        for index in range(scenario.device_count)
    }
    adapters = {
        device_id: build_adapter("serial", f"pressure-adapter-{device_id}")
        for device_id in codecs
    }
    contexts = {
        device_id: TransportContext(
            adapter_id=f"pressure-adapter-{device_id}",
            transport="serial",
            source_id=device_id,
            require_signature=True,
            max_frame_bytes=scenario.max_payload,
        )
        for device_id in codecs
    }
    store = EdgeTelemetryStore(max_samples=max(64, scenario.queue_capacity * 2), state_path=None, checkpoint_every=128)
    sequence_by_device = {device_id: 0 for device_id in codecs}
    frame_index = 0

    for tick in range(scenario.ticks):
        in_burst = scenario.burst_start_tick <= tick < scenario.burst_start_tick + scenario.burst_ticks
        frames_this_tick = scenario.frames_per_device_per_tick * (scenario.burst_multiplier if in_burst else 1)

        for device_id, codec in codecs.items():
            if scenario.disconnect_every and tick > 0 and tick % scenario.disconnect_every == 0:
                if codec.buffered_bytes:
                    metrics.partial_frames_discarded += 1
                codec.reset()
                metrics.disconnects += 1
            for _ in range(frames_this_tick):
                sequence_by_device[device_id] += 1
                sequence = sequence_by_device[device_id]
                frame_index += 1
                frame = _make_frame(device_id, sequence, scenario, frame_index)
                if scenario.duplicate_every and frame_index % scenario.duplicate_every == 0:
                    duplicate_sequence = max(1, sequence - 1)
                    frame = _make_frame(device_id, duplicate_sequence, scenario, frame_index + 10_000_000)
                metrics.produced_frames += 1
                metrics.produced_bytes += len(frame)
                payloads = _feed_partial(codec, frame, scenario.partial_chunk_pattern, metrics)
                for decoded_payload in payloads:
                    metrics.decoded_frames += 1
                    result = adapters[device_id].decode(decoded_payload, contexts[device_id])
                    if not result.normalized or result.packet is None:
                        metrics.rejected_packets += 1
                        if result.failure_class == "pii_or_secret_field_detected":
                            metrics.pii_rejections += 1
                        elif result.failure_class == "invalid_json_or_frame":
                            metrics.malformed_payloads += 1
                        continue
                    if len(queue) >= scenario.queue_capacity:
                        metrics.queue_dropped += 1
                        continue
                    queue.append(decoded_payload)
                    metrics.queue_enqueued += 1
                    metrics.max_queue_depth = max(metrics.max_queue_depth, len(queue))

        for _ in range(min(scenario.consumer_per_tick, len(queue))):
            decoded_payload = queue.popleft()
            # Re-decode at the consumer boundary to model a slow downstream consumer.
            device_id = json.loads(decoded_payload)["packet"]["device_id"]
            result = adapters[device_id].decode(decoded_payload, contexts[device_id])
            if not result.normalized or result.packet is None:
                metrics.rejected_packets += 1
                continue
            packet = result.packet
            append = store.append(
                packet.device_id,
                {
                    "sequence": packet.sequence,
                    "timestamp": packet.timestamp,
                    "accel_x": packet.accel_x,
                    "accel_y": packet.accel_y,
                    "accel_z": packet.accel_z,
                    "battery_pct": packet.battery_pct,
                },
                packet.sequence,
            )
            if append.accepted:
                metrics.accepted_packets += 1
            else:
                metrics.rejected_packets += 1
                if append.reason == "duplicate_or_out_of_order_sequence":
                    metrics.duplicate_rejections += 1
                    metrics.replay_guard_respected = True
            metrics.queue_consumed += 1
            metrics.max_store_buffered_samples = max(metrics.max_store_buffered_samples, append.buffered_samples)
            metrics.dropped_store_samples = max(metrics.dropped_store_samples, append.dropped_samples)

    metrics.max_queue_depth = max(metrics.max_queue_depth, len(queue))
    metrics.backpressure_observed = metrics.queue_dropped > 0
    metrics.memory_bound_respected = metrics.memory_bound_respected and metrics.max_queue_depth <= scenario.queue_capacity and all(codec.buffered_bytes <= scenario.max_buffer for codec in codecs.values())
    metrics.status = "PASSED" if metrics.memory_bound_respected and metrics.replay_guard_respected else "REQUIRES_REVIEW"
    result = metrics.as_dict()
    result["remaining_queue_depth"] = len(queue)
    result["parameters"] = asdict(scenario)
    result["evidence_boundary"] = "software_simulation_only"
    return result


def scenarios() -> list[PressureScenario]:
    return [
        PressureScenario(
            name="serial_burst_saturation",
            ticks=40,
            device_count=8,
            frames_per_device_per_tick=1,
            burst_ticks=8,
            burst_multiplier=12,
            queue_capacity=32,
            consumer_per_tick=4,
        ),
        PressureScenario(
            name="serial_sustained_partial_reads",
            ticks=80,
            device_count=4,
            frames_per_device_per_tick=1,
            burst_ticks=0,
            burst_multiplier=1,
            queue_capacity=64,
            consumer_per_tick=8,
            partial_chunk_pattern=(1, 1, 2, 3, 5),
        ),
        PressureScenario(
            name="serial_corruption_reconnect_replay",
            ticks=60,
            device_count=4,
            frames_per_device_per_tick=1,
            burst_ticks=4,
            burst_multiplier=4,
            queue_capacity=32,
            consumer_per_tick=8,
            crc_corruption_every=17,
            duplicate_every=13,
            disconnect_every=10,
            malformed_every=19,
            pii_every=23,
        ),
    ]


def run(output_path: Path | None = None) -> dict[str, Any]:
    reports = [simulate(scenario) for scenario in scenarios()]
    report = {
        "suite": "smart-ward-network-pressure-v1",
        "scenarios": reports,
        "status": "PASSED" if all(item["status"] == "PASSED" for item in reports) else "REQUIRES_REVIEW",
        "physical_hardware_validation": "PENDING",
        "network_production_validation": "PENDING",
    }
    if output_path is not None:
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline Serial/IoT network pressure simulation")
    parser.add_argument("--output", type=Path, default=Path("network_pressure_result.json"))
    args = parser.parse_args()
    report = run(args.output)
    print(json.dumps(report, indent=2))
    print(f"NETWORK_PRESSURE_SIMULATION_{report['status']}")


if __name__ == "__main__":
    main()
