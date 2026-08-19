from __future__ import annotations

from dataclasses import dataclass
import struct
import zlib


STX = 0x02
ETX = 0x03
FRAME_VERSION = 1
HEADER_SIZE = 5  # STX, version, flags, payload length (uint16)
TRAILER_SIZE = 5  # CRC32 (uint32) and ETX
DEFAULT_MAX_PAYLOAD = 4096


@dataclass(frozen=True)
class FrameEvent:
    kind: str
    payload: bytes | None = None
    detail: str | None = None


class SerialFrameCodec:
    """Incremental, bounded framing for a serial bench transport.

    Wire format:
        STX(1) | VERSION(1) | FLAGS(1) | PAYLOAD_LEN(2, big-endian)
        | PAYLOAD(N) | CRC32(4, big-endian) | ETX(1)

    CRC32 covers VERSION + FLAGS + PAYLOAD_LEN + PAYLOAD. This is an
    integrity check only; it is not authentication. Device Trust remains
    responsible for the Ed25519 signature over the normalized packet.
    """

    def __init__(self, *, max_payload: int = DEFAULT_MAX_PAYLOAD, max_buffer: int | None = None) -> None:
        if max_payload <= 0 or max_payload > 0xFFFF:
            raise ValueError("max_payload must be between 1 and 65535")
        self.max_payload = max_payload
        self.max_buffer = max_buffer or max(HEADER_SIZE + TRAILER_SIZE + max_payload, 2 * (HEADER_SIZE + TRAILER_SIZE + max_payload))
        self._buffer = bytearray()

    @staticmethod
    def encode(payload: bytes, *, flags: int = 0, version: int = FRAME_VERSION, max_payload: int = DEFAULT_MAX_PAYLOAD) -> bytes:
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        if not 0 <= flags <= 255:
            raise ValueError("flags must fit uint8")
        if version != FRAME_VERSION:
            raise ValueError("unsupported frame version")
        if len(payload) > min(max_payload, 0xFFFF):
            raise ValueError("payload exceeds configured maximum")
        header_without_stx = bytes([version, flags]) + struct.pack(">H", len(payload))
        crc = zlib.crc32(header_without_stx + payload) & 0xFFFFFFFF
        return bytes([STX]) + header_without_stx + payload + struct.pack(">I", crc) + bytes([ETX])

    def reset(self) -> None:
        self._buffer.clear()

    def feed(self, chunk: bytes) -> list[FrameEvent]:
        if not isinstance(chunk, bytes):
            raise TypeError("chunk must be bytes")
        events: list[FrameEvent] = []
        if chunk:
            self._buffer.extend(chunk)
        if len(self._buffer) > self.max_buffer:
            stx_index = self._buffer.rfind(bytes([STX]))
            if stx_index >= 0:
                del self._buffer[:stx_index]
            else:
                self._buffer.clear()
            events.append(FrameEvent("buffer_overflow", detail="partial frame buffer exceeded configured bound"))

        while True:
            if not self._buffer:
                break
            try:
                start = self._buffer.index(STX)
            except ValueError:
                self._buffer.clear()
                break
            if start:
                del self._buffer[:start]
                events.append(FrameEvent("noise_discarded"))
            if len(self._buffer) < HEADER_SIZE:
                break
            version = self._buffer[1]
            flags = self._buffer[2]
            payload_len = struct.unpack(">H", self._buffer[3:5])[0]
            if version != FRAME_VERSION:
                del self._buffer[0]
                events.append(FrameEvent("unsupported_version", detail=str(version)))
                continue
            if flags != 0:
                del self._buffer[0]
                events.append(FrameEvent("unsupported_flags", detail=str(flags)))
                continue
            if payload_len > self.max_payload:
                del self._buffer[0]
                events.append(FrameEvent("payload_too_large", detail=str(payload_len)))
                continue
            frame_size = HEADER_SIZE + payload_len + TRAILER_SIZE
            if len(self._buffer) < frame_size:
                break
            candidate = bytes(self._buffer[:frame_size])
            if candidate[-1] != ETX:
                del self._buffer[0]
                events.append(FrameEvent("bad_terminator"))
                continue
            crc_offset = HEADER_SIZE + payload_len
            expected_crc = struct.unpack(">I", candidate[crc_offset:crc_offset + 4])[0]
            actual_crc = zlib.crc32(candidate[1:crc_offset]) & 0xFFFFFFFF
            if expected_crc != actual_crc:
                del self._buffer[0]
                events.append(FrameEvent("crc_mismatch"))
                continue
            payload = candidate[HEADER_SIZE:crc_offset]
            del self._buffer[:frame_size]
            events.append(FrameEvent("frame", payload=payload))
        return events

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)
