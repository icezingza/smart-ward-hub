from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UTC = timezone.utc
RAW_IDENTITY_RE = re.compile(r"(?i)(?<![A-Z0-9])(?:HN|AN|MRN|NATIONAL[_ -]?ID)(?:[:#\s-]+)[A-Z0-9][A-Z0-9_-]{2,}(?![A-Z0-9])")
FORBIDDEN_CLAIM_RE = re.compile(r"(?i)(clinical[-_ ]?ready|production[-_ ]?ready|tamper[-_ ]?proof|authorized[_ -]?by[_ -]?external[_ -]?owner|clinical[_ -]?validated)")


class SimulationApiError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Submission:
    submission_id: str
    request_hash: str
    idempotency_key: str
    package_id: str
    manifest_version: int
    manifest_sha256: str
    scope_id: str
    window_id: str
    status: str = "RECEIVED_FOR_SIMULATION"
    findings: list[dict[str, Any]] = field(default_factory=list)


class SimulatedExternalAuthorizationApi:
    """Offline-only API simulator; it never grants external authorization."""

    def __init__(self, package: dict[str, Any]):
        freeze = package["freeze"]
        self.package_id = package.get("package_id") or package["validation"]["package_id"]
        self.manifest_version = int(freeze["manifest_version"])
        self.manifest_sha256 = str(freeze["manifest_sha256"])
        self.scope_id = str(freeze["scope_id"])
        self.window_id = str(freeze["window_id"])
        self.submissions: dict[str, Submission] = {}
        self.idempotency: dict[str, tuple[str, str]] = {}
        self.audit_events: list[dict[str, Any]] = []
        self._finding_ids: set[str] = set()

    @staticmethod
    def _aware(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise SimulationApiError("REJECTED_TIMEZONE_REQUIRED", "timestamp must be timezone-aware")
        return parsed

    @staticmethod
    def _canonical(value: Any) -> bytes:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()

    @classmethod
    def _hash(cls, value: Any) -> str:
        return hashlib.sha256(cls._canonical(value)).hexdigest()

    @staticmethod
    def _scan_text(value: Any, field_name: str) -> None:
        if isinstance(value, str):
            if RAW_IDENTITY_RE.search(value):
                raise SimulationApiError("REJECTED_RAW_IDENTITY", f"{field_name} contains raw identity")
            if FORBIDDEN_CLAIM_RE.search(value):
                raise SimulationApiError("REJECTED_FORBIDDEN_CLAIM", f"{field_name} contains forbidden claim")
        elif isinstance(value, (tuple, list)):
            for item in value:
                SimulatedExternalAuthorizationApi._scan_text(item, field_name)

    def _record_event(self, action: str, actor_ref: str, payload: dict[str, Any], occurred_at: str) -> dict[str, Any]:
        self._aware(occurred_at)
        self._scan_text(actor_ref, "actor_ref")
        previous = self.audit_events[-1]["event_hash"] if self.audit_events else None
        event = {
            "audit_event_id": f"sim-audit-{len(self.audit_events) + 1:04d}",
            "occurred_at": occurred_at,
            "actor_ref": actor_ref,
            "action": action,
            "payload": payload,
            "previous_event_hash": previous,
            "simulation": True,
            "external_authority": "NONE",
        }
        event["event_hash"] = self._hash(event)
        self.audit_events.append(event)
        return event

    def _response(self, submission: Submission, audit_event_id: str | None = None) -> dict[str, Any]:
        return {
            "submission_id": submission.submission_id,
            "status": submission.status,
            "finding_count": len(submission.findings),
            "simulation": True,
            "external_authority": "NONE",
            "clinical_validation_authorized": False,
            "production_authorized": False,
            "runtime_authority": "NONE",
            "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
            "audit_event_id": audit_event_id,
        }

    def submit(self, request: dict[str, Any]) -> dict[str, Any]:
        required = (
            "submission_idempotency_key",
            "package_id",
            "manifest_version",
            "manifest_sha256",
            "scope_id",
            "window_id",
            "artifact_refs",
            "submitted_by_role",
            "claim_boundary",
            "external_verification_required",
            "submitted_at",
        )
        missing = [key for key in required if key not in request]
        if missing:
            raise SimulationApiError("REJECTED_MISSING_FIELD", f"missing fields: {','.join(missing)}")
        self._aware(str(request["submitted_at"]))
        self._scan_text(request.get("claim_boundary"), "claim_boundary")
        for field_name in ("submission_idempotency_key", "package_id", "scope_id", "window_id", "submitted_by_role"):
            self._scan_text(request[field_name], field_name)
        for ref in request["artifact_refs"]:
            self._scan_text(ref, "artifact_refs")
        if request["external_verification_required"] is not True:
            raise SimulationApiError("REJECTED_VERIFICATION_BYPASS", "external_verification_required must be true")
        if request.get("clinical_validation_authorized") is True or request.get("production_authorized") is True:
            raise SimulationApiError("REJECTED_AUTHORIZATION_ESCALATION", "local submitter cannot self-authorize")
        request_hash = self._hash(request)
        key = request["submission_idempotency_key"]
        if key in self.idempotency:
            existing_id, existing_hash = self.idempotency[key]
            if existing_hash != request_hash:
                raise SimulationApiError("REJECTED_IDEMPOTENCY_CONFLICT", "idempotency key reused with different payload")
            return self._response(self.submissions[existing_id])
        if request["package_id"] != self.package_id:
            raise SimulationApiError("REJECTED_PACKAGE_MISMATCH", "package_id does not match frozen package")
        if int(request["manifest_version"]) != self.manifest_version or request["manifest_sha256"] != self.manifest_sha256:
            raise SimulationApiError("REJECTED_MANIFEST_MISMATCH", "manifest does not match frozen package")
        if request["scope_id"] != self.scope_id or request["window_id"] != self.window_id:
            raise SimulationApiError("REJECTED_SCOPE_WINDOW_MISMATCH", "scope/window does not match freeze")
        submission_id = f"sim-submission-{request_hash[:16]}"
        submission = Submission(
            submission_id=submission_id,
            request_hash=request_hash,
            idempotency_key=key,
            package_id=self.package_id,
            manifest_version=self.manifest_version,
            manifest_sha256=self.manifest_sha256,
            scope_id=self.scope_id,
            window_id=self.window_id,
        )
        self.idempotency[key] = (submission_id, request_hash)
        self.submissions[submission_id] = submission
        event = self._record_event("submit", request["submitted_by_role"], {"submission_id": submission_id, "request_hash": request_hash}, request["submitted_at"])
        return self._response(submission, event["audit_event_id"])

    def poll(self, submission_id: str, occurred_at: str) -> dict[str, Any]:
        self._aware(occurred_at)
        submission = self.submissions[submission_id]
        self._record_event("poll", "local_submitter", {"submission_id": submission_id, "status": submission.status}, occurred_at)
        return self._response(submission)

    def start_review(self, submission_id: str, occurred_at: str) -> dict[str, Any]:
        submission = self.submissions[submission_id]
        if submission.status != "RECEIVED_FOR_SIMULATION":
            raise SimulationApiError("REJECTED_INVALID_STATE", "submission is not awaiting review")
        submission.status = "IN_SIMULATED_REVIEW"
        event = self._record_event("review_start", "simulated_external_reviewer", {"submission_id": submission_id}, occurred_at)
        return self._response(submission, event["audit_event_id"])

    def issue_finding(self, submission_id: str, finding: dict[str, Any], occurred_at: str) -> dict[str, Any]:
        submission = self.submissions[submission_id]
        if submission.status not in {"IN_SIMULATED_REVIEW", "REQUIRES_CLARIFICATION"}:
            raise SimulationApiError("REJECTED_INVALID_STATE", "finding cannot be issued in current state")
        required = ("finding_id", "severity", "category", "summary", "evidence_refs", "required_action", "reviewer_role", "reviewer_identity_ref", "external_verification_status")
        missing = [key for key in required if key not in finding]
        if missing:
            raise SimulationApiError("REJECTED_MISSING_FIELD", f"missing finding fields: {','.join(missing)}")
        for key, value in finding.items():
            self._scan_text(value, key)
        if finding["finding_id"] in self._finding_ids:
            raise SimulationApiError("DUPLICATE_FINDING", "finding_id already exists")
        if finding["external_verification_status"] != "PENDING_EXTERNAL_VERIFICATION":
            raise SimulationApiError("REJECTED_VERIFICATION_BYPASS", "simulated finding must remain externally unverified")
        finding = dict(finding)
        finding["submission_id"] = submission_id
        finding["manifest_sha256"] = submission.manifest_sha256
        finding["scope_id"] = submission.scope_id
        finding["window_id"] = submission.window_id
        finding["simulation"] = True
        self._finding_ids.add(finding["finding_id"])
        submission.findings.append(finding)
        submission.status = "REQUIRES_CLARIFICATION"
        event = self._record_event("finding_issued", "simulated_external_reviewer", {"submission_id": submission_id, "finding_id": finding["finding_id"]}, occurred_at)
        return self._response(submission, event["audit_event_id"])

    def audit(self) -> dict[str, Any]:
        previous = None
        errors: list[str] = []
        for event in self.audit_events:
            expected = self._hash({key: value for key, value in event.items() if key != "event_hash"})
            if event["previous_event_hash"] != previous:
                errors.append(f"previous hash mismatch: {event['audit_event_id']}")
            if event["event_hash"] != expected:
                errors.append(f"event hash mismatch: {event['audit_event_id']}")
            previous = event["event_hash"]
        return {"chain_valid": not errors, "event_count": len(self.audit_events), "errors": errors, "events": self.audit_events}


def load_wave0_package(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    package_path = root / "evals/micro_rag/evidence/wave0-governance-handoff-20260820.json"
    package = load_wave0_package(package_path)
    api = SimulatedExternalAuthorizationApi(package)
    package_id = package.get("package_id") or package["validation"]["package_id"]
    request = {
        "submission_idempotency_key": "wave0-submit-20260820-v1",
        "package_id": package_id,
        "manifest_version": package["freeze"]["manifest_version"],
        "manifest_sha256": package["freeze"]["manifest_sha256"],
        "scope_id": package["freeze"]["scope_id"],
        "window_id": package["freeze"]["window_id"],
        "artifact_refs": ["repo://WAVE_0_GOVERNANCE_HANDOFF_REPORT.md", "repo://WAVE_0_GOVERNANCE_REVIEW_CHECKLIST.md"],
        "submitted_by_role": "evidence_custodian",
        "claim_boundary": "SOFTWARE_VERIFIED_AND_SIMULATION_ONLY; external authorization remains pending",
        "external_verification_required": True,
        "submitted_at": "2026-08-20T08:05:00+00:00",
    }
    received = api.submit(request)
    review = api.start_review(received["submission_id"], "2026-08-20T08:06:00+00:00")
    finding = api.issue_finding(
        received["submission_id"],
        {
            "finding_id": "sim-finding-gv01-001",
            "severity": "HIGH",
            "category": "MISSING_EXTERNAL_GOVERNANCE",
            "summary": "Clinical owner appointment and signed scope remain pending external verification.",
            "evidence_refs": ["repo://WAVE_0_GOVERNANCE_HANDOFF_REPORT.md"],
            "required_action": "Provide external appointment and signed scope with expiry and rollback.",
            "reviewer_role": "independent_reviewer",
            "reviewer_identity_ref": "external-reviewer-ref-001",
            "external_verification_status": "PENDING_EXTERNAL_VERIFICATION",
        },
        "2026-08-20T08:07:00+00:00",
    )
    negative_cases: dict[str, str] = {}
    mutations = {
        "raw_identity": {**request, "submission_idempotency_key": "negative-raw", "artifact_refs": ["repo://HN-1234.txt"]},
        "bad_manifest": {**request, "submission_idempotency_key": "negative-hash", "manifest_sha256": "0" * 64},
        "authorization_escalation": {**request, "submission_idempotency_key": "negative-auth", "clinical_validation_authorized": True},
        "timezone_missing": {**request, "submission_idempotency_key": "negative-time", "submitted_at": "2026-08-20T08:05:00"},
        "verification_bypass": {**request, "submission_idempotency_key": "negative-verification", "external_verification_required": False},
        "idempotency_conflict": {**request, "manifest_sha256": "f" * 64},
    }
    for name, mutation in mutations.items():
        try:
            api.submit(mutation)
        except SimulationApiError as exc:
            negative_cases[name] = exc.code
        else:
            negative_cases[name] = "UNEXPECTED_ACCEPT"
    report = {
        "report_type": "EXTERNAL_AUTHORIZATION_API_SIMULATION",
        "simulation": True,
        "source_boundary": "offline in-memory simulator; no network or credential",
        "positive_lifecycle": {"received": received, "review": review, "finding": finding, "final_poll": api.poll(received["submission_id"], "2026-08-20T08:08:00+00:00")},
        "negative_cases": negative_cases,
        "audit": api.audit(),
        "external_authority": "NONE",
        "clinical_validation_authorized": False,
        "production_authorized": False,
        "runtime_authority": "NONE",
        "pilot_gate_status": "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
    }
    output = root / "evals/micro_rag/evidence/external-authorization-api-simulation-20260820.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "final_status": report["positive_lifecycle"]["final_poll"]["status"], "negative_cases": negative_cases, "audit_chain_valid": report["audit"]["chain_valid"]}, ensure_ascii=False))
