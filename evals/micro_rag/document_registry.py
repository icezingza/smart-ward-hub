from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal


LifecycleState = Literal["DRAFT", "APPROVED", "DEPRECATED", "REVOKED"]
ALLOWED_SCOPES = {"operational", "clinical-governance"}
REGISTRY_SCHEMA_VERSION = "document-registry-v2"
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
    lifecycle_actor_role: str | None = None

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        expiry = _parse_aware_timestamp(self.expires_at, "expires_at")
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


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_aware_timestamp(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise RegistryValidationError(f"invalid_{field_name}") from exc
    if parsed.tzinfo is None:
        raise RegistryValidationError(f"{field_name}_must_be_timezone_aware")
    return parsed


def _scan_text(text: str) -> list[str]:
    return [pattern.pattern for pattern in SENSITIVE_PATTERNS if pattern.search(text)]


class DocumentRegistry:
    """Approved-document registry; deterministic JSON snapshots are portable, not a production authority."""

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
        if record.state not in {"DRAFT", "APPROVED", "DEPRECATED", "REVOKED"}:
            raise RegistryValidationError("invalid lifecycle state")
        if record.state == "APPROVED" and _scan_text(record.text):
            raise RegistryValidationError("approved document failed sensitive-content scan")
        for field_name in ("expires_at", "approved_at", "revoked_at"):
            value = getattr(record, field_name)
            if value is not None:
                _parse_aware_timestamp(value, field_name)
        if record.state == "DRAFT":
            if record.approved_at is not None or record.revoked_at is not None:
                raise RegistryValidationError("draft cannot have approval or revocation timestamp")
        elif record.state in {"APPROVED", "DEPRECATED"}:
            if record.approved_at is None:
                raise RegistryValidationError("approved_or_deprecated_requires_approved_at")
            if record.revoked_at is not None:
                raise RegistryValidationError("non-revoked document cannot have revoked_at")
        elif record.state == "REVOKED":
            if record.approved_at is None or record.revoked_at is None:
                raise RegistryValidationError("revoked_document_requires_approval_and_revocation_timestamps")
        if record.state != "DRAFT":
            if not record.lifecycle_reason or not record.lifecycle_reason.strip():
                raise RegistryValidationError("lifecycle_reason_required")
            if not record.lifecycle_actor_role or not record.lifecycle_actor_role.strip():
                raise RegistryValidationError("lifecycle_actor_role_required")

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
        lifecycle_actor_role: str | None = None,
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
            lifecycle_actor_role=lifecycle_actor_role,
        )
        self._validate_record(record)
        key = (doc_id, version)
        if key in self._records:
            raise RegistryValidationError("doc_id/version already exists; register a new version")
        self._records[key] = record
        return record

    def approve(self, doc_id: str, version: str, reason: str, actor_role: str) -> DocumentRecord:
        record = self.get(doc_id, version)
        if record.state != "DRAFT":
            raise RegistryValidationError("only_draft_document_can_be_approved")
        if not reason.strip():
            raise RegistryValidationError("approval_reason_required")
        if not actor_role.strip():
            raise RegistryValidationError("approval_actor_role_required")
        updated = replace(
            record,
            state="APPROVED",
            approved_at=_now(),
            lifecycle_reason=reason.strip(),
            lifecycle_actor_role=actor_role.strip(),
        )
        self._validate_record(updated)
        self._records[(doc_id, version)] = updated
        return updated

    def deprecate(self, doc_id: str, version: str, reason: str, actor_role: str) -> DocumentRecord:
        record = self.get(doc_id, version)
        if record.state != "APPROVED":
            raise RegistryValidationError("only_approved_document_can_be_deprecated")
        if not reason.strip():
            raise RegistryValidationError("deprecation_reason_required")
        if not actor_role.strip():
            raise RegistryValidationError("deprecation_actor_role_required")
        updated = replace(record, state="DEPRECATED", lifecycle_reason=reason.strip(), lifecycle_actor_role=actor_role.strip())
        self._validate_record(updated)
        self._records[(doc_id, version)] = updated
        return updated

    def revoke(self, doc_id: str, version: str, reason: str, actor_role: str) -> DocumentRecord:
        record = self.get(doc_id, version)
        if record.state not in {"APPROVED", "DEPRECATED"}:
            raise RegistryValidationError("only_approved_or_deprecated_document_can_be_revoked")
        if not reason.strip():
            raise RegistryValidationError("revocation_reason_required")
        if not actor_role.strip():
            raise RegistryValidationError("revocation_actor_role_required")
        updated = replace(
            record,
            state="REVOKED",
            revoked_at=_now(),
            lifecycle_reason=reason.strip(),
            lifecycle_actor_role=actor_role.strip(),
        )
        self._validate_record(updated)
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
        if scope is not None and scope not in ALLOWED_SCOPES:
            raise RegistryValidationError("scope is not approved for query")
        return [record for record in self.records() if record.eligible and (scope is None or record.scope == scope)]

    def manifest(self) -> dict[str, object]:
        return {
            "registry_version": REGISTRY_SCHEMA_VERSION,
            "records": [record.manifest_entry() for record in self.records()],
        }

    def manifest_hash(self) -> str:
        return _canonical_hash(self.manifest())

    def snapshot(self) -> dict[str, object]:
        records = []
        for record in self.records():
            payload = asdict(record)
            payload["languages"] = list(record.languages)
            records.append(payload)
        snapshot = {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "manifest_hash": self.manifest_hash(),
            "records": records,
        }
        snapshot["snapshot_hash"] = _canonical_hash({key: snapshot[key] for key in ("schema_version", "manifest_hash", "records")})
        return snapshot

    def export_json(self, path: str | Path) -> dict[str, object]:
        payload = self.snapshot()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(target)
        return payload

    @classmethod
    def from_snapshot(cls, payload: dict[str, object]) -> "DocumentRegistry":
        expected_keys = {"schema_version", "manifest_hash", "records", "snapshot_hash"}
        if set(payload) != expected_keys:
            raise RegistryValidationError("registry_snapshot_schema_mismatch")
        if payload.get("schema_version") != REGISTRY_SCHEMA_VERSION:
            raise RegistryValidationError("unsupported_registry_snapshot_version")
        records_payload = payload.get("records")
        if not isinstance(records_payload, list):
            raise RegistryValidationError("registry_snapshot_records_required")
        declared_snapshot_hash = payload.get("snapshot_hash")
        calculated_snapshot_hash = _canonical_hash({key: payload[key] for key in ("schema_version", "manifest_hash", "records")})
        if declared_snapshot_hash != calculated_snapshot_hash:
            raise RegistryValidationError("registry_snapshot_hash_mismatch")
        allowed_fields = set(asdict(DocumentRecord(
            doc_id="tmp",
            title="tmp",
            version="tmp",
            owner="tmp",
            source_ref="tmp",
            scope="operational",
            languages=("en",),
            state="DRAFT",
            text="tmp",
            content_sha256=_sha256("tmp"),
        )))
        records: list[DocumentRecord] = []
        for item in records_payload:
            if not isinstance(item, dict) or set(item) != allowed_fields:
                raise RegistryValidationError("registry_record_schema_mismatch")
            item = dict(item)
            languages = item.get("languages")
            if not isinstance(languages, list):
                raise RegistryValidationError("registry_record_languages_must_be_list")
            item["languages"] = tuple(languages)
            records.append(DocumentRecord(**item))
        registry = cls(records)
        if payload.get("manifest_hash") != registry.manifest_hash():
            raise RegistryValidationError("registry_manifest_hash_mismatch")
        return registry

    @classmethod
    def import_json(cls, path: str | Path) -> "DocumentRegistry":
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RegistryValidationError("registry_snapshot_unreadable") from exc
        if not isinstance(payload, dict):
            raise RegistryValidationError("registry_snapshot_object_required")
        return cls.from_snapshot(payload)


__all__ = [
    "ALLOWED_SCOPES",
    "DocumentRecord",
    "DocumentRegistry",
    "LifecycleState",
    "REGISTRY_SCHEMA_VERSION",
    "RegistryValidationError",
]
