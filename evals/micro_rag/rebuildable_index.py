from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from document_registry import ALLOWED_SCOPES, DocumentRecord, DocumentRegistry


INDEX_SCHEMA_VERSION = "rebuildable-index-v2"


class IndexStaleError(RuntimeError):
    pass


class IndexBuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class IndexChunk:
    doc_id: str
    version: str
    chunk_id: str
    chunk_hash: str
    language: str
    scope: str
    text: str


@dataclass(frozen=True)
class IndexHit:
    doc_id: str
    version: str
    chunk_id: str
    chunk_hash: str
    language: str
    scope: str
    score: int
    text: str


class RebuildableIndexAdapter:
    """Deterministic derived index; DocumentRegistry remains authoritative."""

    def __init__(self, *, chunk_chars: int = 800, min_score: int = 2) -> None:
        if chunk_chars < 128:
            raise ValueError("chunk_chars must be at least 128")
        if min_score < 1:
            raise ValueError("min_score must be positive")
        self.chunk_chars = chunk_chars
        self.min_score = min_score
        self._chunks: dict[str, IndexChunk] = {}
        self._registry_manifest_hash: str | None = None
        self._index_hash: str | None = None

    @staticmethod
    def _tokens(value: str) -> set[str]:
        stop_words = {"a", "an", "and", "are", "can", "do", "does", "for", "from", "how", "is", "may", "of", "the", "to", "what", "when", "with"}
        output: set[str] = set()
        for segment in re.findall(r"[a-z0-9_]+|[\u0e00-\u0e7f]+", value.lower()):
            if re.fullmatch(r"[\u0e00-\u0e7f]+", segment):
                output.update(segment[index:index + 2] for index in range(max(0, len(segment) - 1)))
            elif segment not in stop_words and len(segment) > 2:
                output.add(segment)
        return output

    def _chunk_record(self, record: DocumentRecord) -> list[IndexChunk]:
        chunks: list[IndexChunk] = []
        for index in range(0, len(record.text), self.chunk_chars):
            text = record.text[index:index + self.chunk_chars].strip()
            if not text:
                continue
            chunk_id = f"{record.doc_id}:{record.version}:{len(chunks):04d}"
            chunks.append(
                IndexChunk(
                    doc_id=record.doc_id,
                    version=record.version,
                    chunk_id=chunk_id,
                    chunk_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    language="+".join(record.languages),
                    scope=record.scope,
                    text=text,
                )
            )
        if not chunks:
            raise IndexBuildError(f"document produced no chunks: {record.doc_id}/{record.version}")
        return chunks

    @staticmethod
    def _hash_payload(payload: object) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _index_manifest(self, registry_manifest_hash: str, chunks: dict[str, IndexChunk]) -> dict[str, object]:
        return {
            "index_version": INDEX_SCHEMA_VERSION,
            "registry_manifest_hash": registry_manifest_hash,
            "chunk_chars": self.chunk_chars,
            "min_score": self.min_score,
            "chunks": [asdict(chunks[key]) for key in sorted(chunks)],
        }

    def rebuild(self, registry: DocumentRegistry) -> dict[str, object]:
        next_chunks: dict[str, IndexChunk] = {}
        eligible = registry.eligible_records()
        for record in eligible:
            for chunk in self._chunk_record(record):
                if chunk.chunk_id in next_chunks:
                    raise IndexBuildError("duplicate chunk id")
                next_chunks[chunk.chunk_id] = chunk
        next_registry_hash = registry.manifest_hash()
        next_manifest = self._index_manifest(next_registry_hash, next_chunks)
        next_index_hash = self._hash_payload(next_manifest)
        # Commit only after the full derived index and manifest are valid.
        self._chunks = next_chunks
        self._registry_manifest_hash = next_registry_hash
        self._index_hash = next_index_hash
        return {
            "index_version": next_manifest["index_version"],
            "registry_manifest_hash": next_registry_hash,
            "index_hash": next_index_hash,
            "chunk_count": len(next_chunks),
        }

    def _ensure_fresh(self, registry: DocumentRegistry) -> None:
        if self._registry_manifest_hash is None or self._index_hash is None:
            raise IndexStaleError("index has not been built")
        if registry.manifest_hash() != self._registry_manifest_hash:
            raise IndexStaleError("registry changed; rebuild required")
        if self._index_hash != self._hash_payload(self._index_manifest(self._registry_manifest_hash, self._chunks)):
            raise IndexStaleError("index integrity hash mismatch")

    def query(self, query: str, registry: DocumentRegistry, *, scope: str, top_k: int = 5) -> list[IndexHit]:
        if scope not in ALLOWED_SCOPES:
            raise IndexBuildError("scope is not approved for query")
        if top_k < 1 or top_k > 50:
            raise IndexBuildError("top_k must be between 1 and 50")
        self._ensure_fresh(registry)
        query_tokens = self._tokens(query)
        hits: list[IndexHit] = []
        for chunk in self._chunks.values():
            if chunk.scope != scope:
                continue
            score = len(query_tokens & self._tokens(chunk.text))
            if score >= self.min_score:
                hits.append(IndexHit(**asdict(chunk), score=score))
        return sorted(hits, key=lambda item: (-item.score, item.doc_id, item.chunk_id))[:top_k]

    def snapshot_manifest(self) -> dict[str, object]:
        return {
            "index_version": INDEX_SCHEMA_VERSION,
            "registry_manifest_hash": self._registry_manifest_hash,
            "index_hash": self._index_hash,
            "chunk_chars": self.chunk_chars,
            "min_score": self.min_score,
            "chunk_count": len(self._chunks),
        }

    def snapshot(self) -> dict[str, object]:
        if self._registry_manifest_hash is None or self._index_hash is None:
            raise IndexStaleError("index has not been built")
        payload: dict[str, object] = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "registry_manifest_hash": self._registry_manifest_hash,
            "index_hash": self._index_hash,
            "chunk_chars": self.chunk_chars,
            "min_score": self.min_score,
            "chunks": [asdict(self._chunks[key]) for key in sorted(self._chunks)],
        }
        payload["snapshot_hash"] = self._hash_payload({key: payload[key] for key in payload if key != "snapshot_hash"})
        return payload

    def export_json(self, path: str | Path) -> dict[str, object]:
        payload = self.snapshot()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(target)
        return payload

    @classmethod
    def from_snapshot(cls, payload: dict[str, object], registry: DocumentRegistry) -> "RebuildableIndexAdapter":
        expected_keys = {"schema_version", "registry_manifest_hash", "index_hash", "chunk_chars", "min_score", "chunks", "snapshot_hash"}
        if set(payload) != expected_keys:
            raise IndexBuildError("index_snapshot_schema_mismatch")
        if payload.get("schema_version") != INDEX_SCHEMA_VERSION:
            raise IndexBuildError("unsupported_index_snapshot_version")
        if payload.get("registry_manifest_hash") != registry.manifest_hash():
            raise IndexStaleError("registry manifest does not match index snapshot")
        chunks_payload = payload.get("chunks")
        if not isinstance(chunks_payload, list):
            raise IndexBuildError("index_snapshot_chunks_required")
        declared_snapshot_hash = payload.get("snapshot_hash")
        calculated_snapshot_hash = cls._hash_payload({key: payload[key] for key in payload if key != "snapshot_hash"})
        if declared_snapshot_hash != calculated_snapshot_hash:
            raise IndexBuildError("index_snapshot_hash_mismatch")
        chunk_chars = payload.get("chunk_chars")
        min_score = payload.get("min_score")
        if not isinstance(chunk_chars, int) or not isinstance(min_score, int):
            raise IndexBuildError("index_snapshot_config_invalid")
        adapter = cls(chunk_chars=chunk_chars, min_score=min_score)
        chunks: dict[str, IndexChunk] = {}
        allowed_chunk_fields = {"doc_id", "version", "chunk_id", "chunk_hash", "language", "scope", "text"}
        for item in chunks_payload:
            if not isinstance(item, dict) or set(item) != allowed_chunk_fields:
                raise IndexBuildError("index_chunk_schema_mismatch")
            chunk = IndexChunk(**item)
            if chunk.chunk_id in chunks:
                raise IndexBuildError("duplicate chunk id")
            if chunk.chunk_hash != hashlib.sha256(chunk.text.encode("utf-8")).hexdigest():
                raise IndexBuildError("chunk_hash_mismatch")
            match = re.fullmatch(r"([a-z0-9][a-z0-9._-]{2,127}):([^:]+):(\d{4})", chunk.chunk_id)
            if not match or match.group(1) != chunk.doc_id or match.group(2) != chunk.version:
                raise IndexBuildError("chunk_id_mismatch")
            try:
                record = registry.get(chunk.doc_id, chunk.version)
            except Exception as exc:
                raise IndexStaleError("index chunk references unknown registry record") from exc
            if not record.eligible or record.scope != chunk.scope or "+".join(record.languages) != chunk.language:
                raise IndexStaleError("index chunk references ineligible or mismatched registry record")
            if chunk.text not in record.text:
                raise IndexBuildError("chunk_text_not_found_in_registry_record")
            chunks[chunk.chunk_id] = chunk
        expected_index_hash = adapter._hash_payload(adapter._index_manifest(str(payload["registry_manifest_hash"]), chunks))
        if payload.get("index_hash") != expected_index_hash:
            raise IndexBuildError("index_hash_mismatch")
        adapter._chunks = chunks
        adapter._registry_manifest_hash = str(payload["registry_manifest_hash"])
        adapter._index_hash = str(payload["index_hash"])
        return adapter

    @classmethod
    def import_json(cls, path: str | Path, registry: DocumentRegistry) -> "RebuildableIndexAdapter":
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexBuildError("index_snapshot_unreadable") from exc
        if not isinstance(payload, dict):
            raise IndexBuildError("index_snapshot_object_required")
        return cls.from_snapshot(payload, registry)

    def clear(self) -> None:
        self._chunks = {}
        self._registry_manifest_hash = None
        self._index_hash = None


__all__ = [
    "INDEX_SCHEMA_VERSION",
    "IndexBuildError",
    "IndexChunk",
    "IndexHit",
    "IndexStaleError",
    "RebuildableIndexAdapter",
]
