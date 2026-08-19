from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Iterable

from document_registry import DocumentRecord, DocumentRegistry


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
    """Deterministic derived index; the DocumentRegistry remains authoritative."""

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

    def rebuild(self, registry: DocumentRegistry) -> dict[str, object]:
        next_chunks: dict[str, IndexChunk] = {}
        eligible = registry.eligible_records()
        for record in eligible:
            for chunk in self._chunk_record(record):
                if chunk.chunk_id in next_chunks:
                    raise IndexBuildError("duplicate chunk id")
                next_chunks[chunk.chunk_id] = chunk
        next_registry_hash = registry.manifest_hash()
        next_manifest = {
            "index_version": "rebuildable-index-v1",
            "registry_manifest_hash": next_registry_hash,
            "chunk_chars": self.chunk_chars,
            "min_score": self.min_score,
            "chunks": [asdict(next_chunks[key]) for key in sorted(next_chunks)],
        }
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

    def query(self, query: str, registry: DocumentRegistry, *, scope: str, top_k: int = 5) -> list[IndexHit]:
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
            "index_version": "rebuildable-index-v1",
            "registry_manifest_hash": self._registry_manifest_hash,
            "index_hash": self._index_hash,
            "chunk_count": len(self._chunks),
        }

    def clear(self) -> None:
        self._chunks = {}
        self._registry_manifest_hash = None
        self._index_hash = None
