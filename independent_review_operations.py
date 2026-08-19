from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any

from gv10_evidence import EvidenceEntry, GV10EvidenceError, VALID_GATE_IDS


SAFE_REF = re.compile(r"[A-Za-z0-9._:/-]{1,200}")
RAW_ID = re.compile(r"\b(?:HN|AN|MRN|NATIONAL_ID)\s*[-_:]?\s*[A-Z0-9-]+\b", re.IGNORECASE)
VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
VALID_OUTCOMES = {
    "ACCEPTED_FOR_REVIEW",
    "REQUIRES_CLARIFICATION",
    "BLOCKED_EXTERNAL_EVIDENCE",
    "REJECTED",
}


class ReviewOperationError(ValueError):
    pass


def _validate_ref(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not SAFE_REF.fullmatch(value) or RAW_ID.search(value):
        raise ReviewOperationError(f"unsafe_{field_name}")


def _validate_aware_timestamp(value: str, field_name: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewOperationError(f"invalid_{field_name}") from exc
    if parsed.tzinfo is None:
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
        severity = self.severity.strip().upper()
        if severity not in VALID_SEVERITIES:
            raise ReviewOperationError("invalid_finding_severity")
        outcome = self.outcome.strip().upper()
        if outcome not in VALID_OUTCOMES:
            raise ReviewOperationError("invalid_finding_outcome")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ReviewOperationError("finding_summary_required")
        if RAW_ID.search(self.summary):
            raise ReviewOperationError("raw_identity_in_finding_summary")
        if not self.evidence_ids:
            raise ReviewOperationError("finding_evidence_trace_required")
        seen: set[str] = set()
        for evidence_id in self.evidence_ids:
            _validate_ref(evidence_id, "finding_evidence_id")
            if evidence_id in seen:
                raise ReviewOperationError("duplicate_finding_evidence_id")
            seen.add(evidence_id)
        if not self.issued_by_role.strip():
            raise ReviewOperationError("finding_issuer_role_required")
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

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _validate_ref(self.session_id, "session_id")
        _validate_ref(self.dossier_id, "dossier_id")
        if self.reviewer_role.strip() == "":
            raise ReviewOperationError("reviewer_role_required")
        _validate_aware_timestamp(self.opened_at_utc, "opened_timestamp")
        if self.status not in {"OPEN", "CLOSED"}:
            raise ReviewOperationError("invalid_review_session_status")
        if self.clinical_validation_authorized is not False:
            raise ReviewOperationError("clinical_authorization_forbidden")
        if self.production_authorized is not False:
            raise ReviewOperationError("production_authorization_forbidden")
        if self.status == "CLOSED":
            if not self.closed_at_utc:
                raise ReviewOperationError("closed_timestamp_required")
            _validate_aware_timestamp(self.closed_at_utc, "closed_timestamp")
        elif self.closed_at_utc is not None:
            raise ReviewOperationError("open_session_cannot_have_closed_timestamp")
        for evidence_id, entry in self.accepted_evidence.items():
            _validate_ref(evidence_id, "accepted_evidence_id")
            try:
                entry.validate()
            except GV10EvidenceError as exc:
                raise ReviewOperationError(f"invalid_accepted_evidence:{exc}") from exc
            if evidence_id != entry.evidence_id:
                raise ReviewOperationError("accepted_evidence_key_mismatch")
        for finding_id, finding in self.findings.items():
            finding.validate()
            if finding_id != finding.finding_id:
                raise ReviewOperationError("finding_key_mismatch")
            for evidence_id in finding.evidence_ids:
                entry = self.accepted_evidence.get(evidence_id)
                if entry is None:
                    raise ReviewOperationError("finding_references_unaccepted_evidence")
                if entry.gate_id != finding.gate_id:
                    raise ReviewOperationError("finding_gate_evidence_mismatch")

    def _require_open(self) -> None:
        if self.status != "OPEN":
            raise ReviewOperationError("review_session_closed")

    def accept_evidence(self, entry: EvidenceEntry) -> None:
        self.validate()
        self._require_open()
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
        return self.summary()

    def authorization_boundary(self) -> dict[str, bool]:
        return {
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "real_world_authorization": False,
        }

    def authorize_clinical_validation(self) -> None:
        raise ReviewOperationError("clinical_authorization_requires_external_governance")

    def authorize_production(self) -> None:
        raise ReviewOperationError("production_authorization_requires_external_governance")

    def summary(self) -> dict[str, Any]:
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
