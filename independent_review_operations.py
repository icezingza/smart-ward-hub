from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from gv10_evidence import EvidenceEntry, GV10EvidenceError, VALID_GATE_IDS


SAFE_REF = re.compile(r"[A-Za-z0-9._:/-]{1,200}")
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)(?:\s*[-_:]\s*[A-Z0-9-]{2,}|\s+\d[A-Z0-9-]{1,})\b", re.IGNORECASE)
RAW_CONTACT = re.compile(r"(?:@|(?<![A-Za-z0-9])\+?\d[\d\s().-]{7,}\d(?![A-Za-z0-9]))")
SECRET_MARKER = re.compile(r"(?:BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY|Bearer\s+\S+|(?:password|secret|token|private_key|seed)\s*[:=]\s*\S+)", re.IGNORECASE)
VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
VALID_OUTCOMES = {
    "ACCEPTED_FOR_REVIEW",
    "REQUIRES_CLARIFICATION",
    "BLOCKED_EXTERNAL_EVIDENCE",
    "REJECTED",
}


class ReviewOperationError(ValueError):
    pass


def _validate_ref(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not SAFE_REF.fullmatch(value.strip()) or RAW_ID.search(value) or RAW_CONTACT.search(value) or SECRET_MARKER.search(value):
        raise ReviewOperationError(f"unsafe_{field_name}")


def _validate_role(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip() or RAW_ID.search(value) or RAW_CONTACT.search(value) or SECRET_MARKER.search(value):
        raise ReviewOperationError(f"{field_name}_required")


def _validate_safe_text(value: Any, field_name: str, *, max_length: int = 1024) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ReviewOperationError(f"{field_name}_invalid")
    if RAW_ID.search(value):
        raise ReviewOperationError(f"raw_identity_in_{field_name}")
    if RAW_CONTACT.search(value):
        raise ReviewOperationError(f"raw_contact_in_{field_name}")
    if SECRET_MARKER.search(value):
        raise ReviewOperationError(f"secret_marker_in_{field_name}")


def _validate_aware_timestamp(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise ReviewOperationError(f"invalid_{field_name}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ReviewOperationError(f"invalid_{field_name}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewOperationError(f"{field_name}_must_be_timezone_aware")


@dataclass(frozen=True)
class ReviewFinding:
    finding_id: str
    gate_id: str
    severity: str
    outcome: str
    summary: str
    evidence_ids: tuple[str, ...]
    issued_at_utc: str
    issued_by_role: str

    def validate(self) -> None:
        _validate_ref(self.finding_id, "finding_id")
        if self.gate_id not in VALID_GATE_IDS:
            raise ReviewOperationError("unknown_finding_gate_id")
        if not isinstance(self.severity, str) or self.severity.strip().upper() not in VALID_SEVERITIES:
            raise ReviewOperationError("invalid_finding_severity")
        if not isinstance(self.outcome, str) or self.outcome.strip().upper() not in VALID_OUTCOMES:
            raise ReviewOperationError("invalid_finding_outcome")
        _validate_safe_text(self.summary, "finding_summary", max_length=1024)
        if not isinstance(self.evidence_ids, (tuple, list)) or not self.evidence_ids:
            raise ReviewOperationError("finding_evidence_trace_required")
        seen: set[str] = set()
        for evidence_id in self.evidence_ids:
            _validate_ref(evidence_id, "finding_evidence_id")
            if evidence_id in seen:
                raise ReviewOperationError("duplicate_finding_evidence_id")
            seen.add(evidence_id)
        _validate_role(self.issued_by_role, "finding_issuer_role")
        _validate_aware_timestamp(self.issued_at_utc, "finding_timestamp")


@dataclass
class IndependentReviewSession:
    session_id: str
    dossier_id: str
    reviewer_role: str
    opened_at_utc: str
    status: str = "OPEN"
    accepted_evidence: dict[str, EvidenceEntry] = field(default_factory=dict)
    findings: dict[str, ReviewFinding] = field(default_factory=dict)
    closed_at_utc: str | None = None
    clinical_validation_authorized: bool = False
    production_authorized: bool = False
    real_world_authorization: bool = False
    pilot_gate_status: str = "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    _closed_fingerprint: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.validate()

    def _state_fingerprint(self) -> str:
        evidence_payload = {
            evidence_id: {
                "evidence_id": entry.evidence_id,
                "gate_id": entry.gate_id,
                "artifact_ref": entry.artifact_ref,
                "artifact_sha256": entry.artifact_sha256,
                "evidence_class": entry.evidence_class,
                "collected_at_utc": entry.collected_at_utc,
                "prepared_by_role": entry.prepared_by_role,
                "source_boundary": entry.source_boundary,
                "redaction_status": entry.redaction_status,
                "chain_of_custody_ref": entry.chain_of_custody_ref,
                "independent_verification_required": entry.independent_verification_required,
            }
            for evidence_id, entry in sorted(self.accepted_evidence.items())
        }
        finding_payload = {
            finding_id: {
                "finding_id": finding.finding_id,
                "gate_id": finding.gate_id,
                "severity": finding.severity,
                "outcome": finding.outcome,
                "summary": finding.summary,
                "evidence_ids": list(finding.evidence_ids),
                "issued_at_utc": finding.issued_at_utc,
                "issued_by_role": finding.issued_by_role,
            }
            for finding_id, finding in sorted(self.findings.items())
        }
        payload = {
            "session_id": self.session_id,
            "dossier_id": self.dossier_id,
            "reviewer_role": self.reviewer_role,
            "opened_at_utc": self.opened_at_utc,
            "status": self.status,
            "closed_at_utc": self.closed_at_utc,
            "clinical_validation_authorized": self.clinical_validation_authorized,
            "production_authorized": self.production_authorized,
            "real_world_authorization": self.real_world_authorization,
            "pilot_gate_status": self.pilot_gate_status,
            "accepted_evidence": evidence_payload,
            "findings": finding_payload,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def validate(self) -> None:
        _validate_ref(self.session_id, "session_id")
        _validate_ref(self.dossier_id, "dossier_id")
        _validate_role(self.reviewer_role, "reviewer_role")
        _validate_aware_timestamp(self.opened_at_utc, "opened_timestamp")
        if self._closed_fingerprint is not None and self.status != "CLOSED":
            raise ReviewOperationError("closed_review_state_mutated")
        if self.status not in {"OPEN", "CLOSED"}:
            raise ReviewOperationError("invalid_review_session_status")
        if self.clinical_validation_authorized is not False:
            raise ReviewOperationError("clinical_authorization_forbidden")
        if self.production_authorized is not False:
            raise ReviewOperationError("production_authorization_forbidden")
        if self.real_world_authorization is not False:
            raise ReviewOperationError("real_world_authorization_forbidden")
        if self.pilot_gate_status != "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION":
            raise ReviewOperationError("pilot_gate_authorization_forbidden")
        if self.status == "CLOSED":
            if not self.closed_at_utc:
                raise ReviewOperationError("closed_timestamp_required")
            _validate_aware_timestamp(self.closed_at_utc, "closed_timestamp")
        elif self.closed_at_utc is not None:
            raise ReviewOperationError("open_session_cannot_have_closed_timestamp")
        if not isinstance(self.accepted_evidence, dict):
            raise ReviewOperationError("accepted_evidence_registry_must_be_dict")
        for evidence_id, entry in self.accepted_evidence.items():
            _validate_ref(evidence_id, "accepted_evidence_id")
            if not isinstance(entry, EvidenceEntry):
                raise ReviewOperationError("invalid_accepted_evidence_record")
            try:
                entry.validate()
            except GV10EvidenceError as exc:
                raise ReviewOperationError(f"invalid_accepted_evidence:{exc}") from exc
            if evidence_id != entry.evidence_id:
                raise ReviewOperationError("accepted_evidence_key_mismatch")
        if not isinstance(self.findings, dict):
            raise ReviewOperationError("finding_registry_must_be_dict")
        for finding_id, finding in self.findings.items():
            if not isinstance(finding, ReviewFinding):
                raise ReviewOperationError("invalid_finding_record")
            finding.validate()
            if finding_id != finding.finding_id:
                raise ReviewOperationError("finding_key_mismatch")
            for evidence_id in finding.evidence_ids:
                entry = self.accepted_evidence.get(evidence_id)
                if entry is None:
                    raise ReviewOperationError("finding_references_unaccepted_evidence")
                if entry.gate_id != finding.gate_id:
                    raise ReviewOperationError("finding_gate_evidence_mismatch")
        if self._closed_fingerprint is not None:
            if self.status != "CLOSED" or self.closed_at_utc is None:
                raise ReviewOperationError("closed_review_state_mutated")
            if self._state_fingerprint() != self._closed_fingerprint:
                raise ReviewOperationError("closed_review_state_mutated")

    def _require_open(self) -> None:
        if self.status != "OPEN":
            raise ReviewOperationError("review_session_closed")

    def accept_evidence(self, entry: EvidenceEntry) -> None:
        self.validate()
        self._require_open()
        if not isinstance(entry, EvidenceEntry):
            raise ReviewOperationError("invalid_evidence_record")
        try:
            entry.validate()
        except GV10EvidenceError as exc:
            raise ReviewOperationError(f"invalid_evidence:{exc}") from exc
        if entry.evidence_id in self.accepted_evidence:
            raise ReviewOperationError("duplicate_accepted_evidence")
        self.accepted_evidence[entry.evidence_id] = entry

    def issue_finding(self, finding: ReviewFinding) -> None:
        self.validate()
        self._require_open()
        if not isinstance(finding, ReviewFinding):
            raise ReviewOperationError("invalid_finding_record")
        finding.validate()
        if finding.finding_id in self.findings:
            raise ReviewOperationError("duplicate_finding_id")
        for evidence_id in finding.evidence_ids:
            entry = self.accepted_evidence.get(evidence_id)
            if entry is None:
                raise ReviewOperationError("finding_references_unaccepted_evidence")
            if entry.gate_id != finding.gate_id:
                raise ReviewOperationError("finding_gate_evidence_mismatch")
        self.findings[finding.finding_id] = finding

    def close(self, closed_at_utc: str | None = None) -> dict[str, Any]:
        self.validate()
        self._require_open()
        if not self.accepted_evidence:
            raise ReviewOperationError("cannot_close_without_accepted_evidence")
        timestamp = closed_at_utc or datetime.now(timezone.utc).isoformat()
        _validate_aware_timestamp(timestamp, "closed_timestamp")
        self.status = "CLOSED"
        self.closed_at_utc = timestamp
        self._closed_fingerprint = self._state_fingerprint()
        return self.summary()

    def authorization_boundary(self) -> dict[str, Any]:
        return {
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "real_world_authorization": False,
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        }

    def authorize_clinical_validation(self) -> None:
        raise ReviewOperationError("clinical_authorization_requires_external_governance")

    def authorize_production(self) -> None:
        raise ReviewOperationError("production_authorization_requires_external_governance")

    def authorize_pilot(self) -> None:
        raise ReviewOperationError("pilot_authorization_requires_external_governance")

    def summary(self) -> dict[str, Any]:
        self.validate()
        return {
            "session_id": self.session_id,
            "dossier_id": self.dossier_id,
            "reviewer_role": self.reviewer_role,
            "status": self.status,
            "accepted_evidence_count": len(self.accepted_evidence),
            "finding_count": len(self.findings),
            "finding_severity_counts": {
                severity: sum(1 for finding in self.findings.values() if finding.severity.strip().upper() == severity)
                for severity in sorted(VALID_SEVERITIES)
            },
            "gate_ids_reviewed": sorted({entry.gate_id for entry in self.accepted_evidence.values()}),
            "authorization_boundary": self.authorization_boundary(),
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
            "review_outcome": "CLOSED_WITH_FINDINGS" if self.status == "CLOSED" and self.findings else (
                "CLOSED_NO_FINDINGS" if self.status == "CLOSED" else "OPEN"
            ),
        }


def open_review_session(
    *,
    session_id: str,
    dossier_id: str,
    reviewer_role: str = "independent_reviewer",
    opened_at_utc: str | None = None,
) -> IndependentReviewSession:
    return IndependentReviewSession(
        session_id=session_id,
        dossier_id=dossier_id,
        reviewer_role=reviewer_role,
        opened_at_utc=opened_at_utc or datetime.now(timezone.utc).isoformat(),
    )


__all__ = [
    "IndependentReviewSession",
    "ReviewFinding",
    "ReviewOperationError",
    "open_review_session",
]
