from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Iterable, Literal


LifecycleState = Literal["DRAFT", "APPROVED", "DEPRECATED", "REVOKED"]
ALLOWED_SCOPES = {"operational", "clinical-governance"}
SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:HN|AN)[-:/][A-Za-z0-9_-]+\b"),
    re.compile(r"\bpatient[_ ]name\b", re.IGNORECASE),
    re.compile(r"\bnational[_ ]id\b", re.IGNORECASE),
    re.compile(r"\bpatient_token\s*[:=]", re.IGNORECASE),
    re.compile(r"Authorization\s*:\s*Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


class RegistryValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DocumentRecord:
    doc_id: str
    title: str
    version: str
    owner: str
    source_ref: str
    scope: str
    languages: tuple[str, ...]
    state: LifecycleState
    text: str
    content_sha256: str
    contains_pii: bool = False
    contains_secret: bool = False
    expires_at: str | None = None
    approved_at: str | None = None
    revoked_at: str | None = None
    lifecycle_reason: str | None = None

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        return expiry <= datetime.now(timezone.utc)

    @property
    def eligible(self) -> bool:
        return (
            self.state == "APPROVED"
            and self.scope in ALLOWED_SCOPES
            and not self.contains_pii
            and not self.contains_secret
            and not self.is_expired
        )

    def manifest_entry(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("text", None)
        payload["languages"] = list(self.languages)
        payload["eligible"] = self.eligible
        return payload


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scan_text(text: str) -> list[str]:
    return [pattern.pattern for pattern in SENSITIVE_PATTERNS if pattern.search(text)]


class DocumentRegistry:
    """In-memory approved-document registry; the index is always derived from it."""

    def __init__(self, records: Iterable[DocumentRecord] = ()) -> None:
        self._records: dict[tuple[str, str], DocumentRecord] = {}
        for record in records:
            self._validate_record(record)
            key = (record.doc_id, record.version)
            if key in self._records:
                raise RegistryValidationError("duplicate doc_id/version")
            self._records[key] = record

    @staticmethod
    def _validate_record(record: DocumentRecord) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,127}", record.doc_id):
            raise RegistryValidationError("invalid doc_id")
        if not record.title.strip() or not record.version.strip() or not record.owner.strip() or not record.source_ref.strip():
            raise RegistryValidationError("title/version/owner/source_ref are required")
        if record.scope not in ALLOWED_SCOPES:
            raise RegistryValidationError("scope is not approved for initial Micro-RAG")
        if not record.languages or any(not language.strip() for language in record.languages):
            raise RegistryValidationError("at least one language is required")
        if not record.text.strip():
            raise RegistryValidationError("document text is required")
        if record.content_sha256 != _sha256(record.text):
            raise RegistryValidationError("content_sha256 mismatch")
        if record.contains_pii or record.contains_secret:
            raise RegistryValidationError("PII or secret-bearing document cannot enter registry")
        if record.state == "APPROVED" and _scan_text(record.text):
            raise RegistryValidationError("approved document failed sensitive-content scan")

    def register(
        self,
        *,
        doc_id: str,
        title: str,
        version: str,
        owner: str,
        source_ref: str,
        scope: str,
        languages: Iterable[str],
        text: str,
        state: LifecycleState = "DRAFT",
        expires_at: str | None = None,
        lifecycle_reason: str | None = None,
    ) -> DocumentRecord:
        if state == "APPROVED" and _scan_text(text):
            raise RegistryValidationError("approved document failed sensitive-content scan")
        timestamp = _now() if state == "APPROVED" else None
        record = DocumentRecord(
            doc_id=doc_id,
            title=title,
            version=version,
            owner=owner,
            source_ref=source_ref,
            scope=scope,
            languages=tuple(languages),
            state=state,
            text=text,
            content_sha256=_sha256(text),
            expires_at=expires_at,
            approved_at=timestamp,
            lifecycle_reason=lifecycle_reason,
        )
        self._validate_record(record)
        key = (doc_id, version)
        if key in self._records:
            raise RegistryValidationError("doc_id/version already exists; register a new version")
        self._records[key] = record
        return record

    def approve(self, doc_id: str, version: str, reason: str) -> DocumentRecord:
        record = self.get(doc_id, version)
        if record.state == "REVOKED":
            raise RegistryValidationError("revoked document cannot be re-approved")
        updated = replace(record, state="APPROVED", approved_at=_now(), lifecycle_reason=reason)
        self._validate_record(updated)
        self._records[(doc_id, version)] = updated
        return updated

    def deprecate(self, doc_id: str, version: str, reason: str) -> DocumentRecord:
        record = self.get(doc_id, version)
        updated = replace(record, state="DEPRECATED", lifecycle_reason=reason)
        self._records[(doc_id, version)] = updated
        return updated

    def revoke(self, doc_id: str, version: str, reason: str) -> DocumentRecord:
        record = self.get(doc_id, version)
        updated = replace(record, state="REVOKED", revoked_at=_now(), lifecycle_reason=reason)
        self._records[(doc_id, version)] = updated
        return updated

    def get(self, doc_id: str, version: str) -> DocumentRecord:
        try:
            return self._records[(doc_id, version)]
        except KeyError as exc:
            raise RegistryValidationError("document version not found") from exc

    def records(self) -> list[DocumentRecord]:
        return [self._records[key] for key in sorted(self._records)]

    def eligible_records(self, scope: str | None = None) -> list[DocumentRecord]:
        return [record for record in self.records() if record.eligible and (scope is None or record.scope == scope)]

    def manifest(self) -> dict[str, object]:
        return {
            "registry_version": "document-registry-v1",
            "records": [record.manifest_entry() for record in self.records()],
        }

    def manifest_hash(self) -> str:
        encoded = json.dumps(self.manifest(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
