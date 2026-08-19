from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from persistence_contract import PersistencePolicy, PersistencePolicyError


@dataclass(frozen=True)
class ReadinessCheck:
    check_id: str
    passed: bool
    evidence_class: str
    reason: str


@dataclass(frozen=True)
class ReadinessDecision:
    status: str
    checks: tuple[ReadinessCheck, ...]
    clinical_validation_authorized: bool
    production_authorized: bool
    runtime_authority: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": [asdict(check) for check in self.checks],
            "clinical_validation_authorized": self.clinical_validation_authorized,
            "production_authorized": self.production_authorized,
            "runtime_authority": self.runtime_authority,
        }


def _check(check_id: str, passed: bool, reason: str, evidence_class: str = "SOFTWARE_VERIFIED") -> ReadinessCheck:
    return ReadinessCheck(check_id=check_id, passed=passed, evidence_class=evidence_class, reason=reason)


def evaluate_runtime_readiness(
    *,
    registry: Any,
    index: Any,
    persistence_policy: PersistencePolicy,
    repeated_summary: dict[str, Any],
    runtime_backend_configured: bool = False,
    access_control_enforced: bool = False,
    clinical_governance_review_complete: bool = False,
    external_persistence_approved: bool = False,
) -> ReadinessDecision:
    checks: list[ReadinessCheck] = []

    try:
        policy = persistence_policy.software_verify()
        policy_valid = True
        policy_reason = "persistence policy validates as software-only metadata"
    except PersistencePolicyError as exc:
        policy_valid = False
        policy_reason = str(exc)
    checks.append(_check("persistence_policy_valid", policy_valid, policy_reason))

    registry_hash = registry.manifest_hash()
    index_snapshot = index.snapshot_manifest()
    checks.append(
        _check(
            "registry_index_manifest_match",
            bool(index_snapshot.get("registry_manifest_hash") == registry_hash and index_snapshot.get("index_hash")),
            "index is built from the current registry manifest" if index_snapshot.get("registry_manifest_hash") == registry_hash else "index registry manifest is stale or missing",
        )
    )
    eligible_records = registry.eligible_records()
    checks.append(
        _check(
            "eligible_corpus_zero_pii",
            bool(eligible_records) and all(not record.contains_pii and not record.contains_secret for record in eligible_records),
            "eligible registry records are non-empty and contain no PII/secret flags" if eligible_records and all(not record.contains_pii and not record.contains_secret for record in eligible_records) else "eligible corpus is empty or contains prohibited flags",
        )
    )

    repeated_status = repeated_summary.get("status")
    checks.append(
        _check(
            "repeated_model_sample_gate",
            repeated_status == "REPEATED_EVALUATED_WITH_ADAPTER",
            "repeated compatible samples meet the model-evaluation contract" if repeated_status == "REPEATED_EVALUATED_WITH_ADAPTER" else f"repeated model evidence status is {repeated_status or 'MISSING'}",
            "SOFTWARE_VERIFIED" if repeated_status == "REPEATED_EVALUATED_WITH_ADAPTER" else "SIMULATION_ONLY",
        )
    )
    checks.append(
        _check(
            "runtime_semantic_backend_configured",
            runtime_backend_configured is True,
            "runtime semantic backend is configured" if runtime_backend_configured else "runtime semantic backend is not configured by this software baseline",
            "EXTERNAL_UNVERIFIED" if not runtime_backend_configured else "SOFTWARE_VERIFIED",
        )
    )
    checks.append(
        _check(
            "runtime_access_control_enforced",
            access_control_enforced is True,
            "runtime access control is enforced" if access_control_enforced else "runtime access-control enforcement is not evidenced",
            "EXTERNAL_UNVERIFIED" if not access_control_enforced else "SOFTWARE_VERIFIED",
        )
    )
    checks.append(
        _check(
            "external_persistence_approval",
            external_persistence_approved is True,
            "external persistence owner and retention approval is evidenced" if external_persistence_approved else "external persistence owner/retention approval is not evidenced",
            "EXTERNAL_UNVERIFIED" if not external_persistence_approved else "SOFTWARE_VERIFIED",
        )
    )
    checks.append(
        _check(
            "clinical_governance_boundary",
            clinical_governance_review_complete is True,
            "clinical retrieval governance review is complete" if clinical_governance_review_complete else "clinical retrieval governance review is pending",
            "CLINICAL_GOVERNANCE_UNVERIFIED" if not clinical_governance_review_complete else "SOFTWARE_VERIFIED",
        )
    )

    # Local software checks never grant authority. Deployment readiness remains closed until all external checks pass.
    all_passed = all(check.passed for check in checks)
    status = "READY_FOR_EXTERNAL_GOVERNANCE_REVIEW" if all_passed else "NOT_READY"
    return ReadinessDecision(
        status=status,
        checks=tuple(checks),
        clinical_validation_authorized=False,
        production_authorized=False,
        runtime_authority="NONE",
    )


__all__ = ["ReadinessCheck", "ReadinessDecision", "evaluate_runtime_readiness"]
