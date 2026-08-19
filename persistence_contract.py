from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Literal


POLICY_VERSION = "p2-004-persistence-v1"
ARTIFACT_TYPES = {"registry_snapshot", "index_snapshot"}
STORAGE_CLASSES = {"local_ephemeral", "local_encrypted", "managed_object_store", "external_worm"}
ACCESS_MODES = {"read_only", "append_only", "controlled_write"}
INTEGRITY_METHODS = {"sha256_manifest", "signed_manifest", "external_receipt"}
APPROVAL_STATES = {"UNAPPROVED", "SOFTWARE_VERIFIED", "EXTERNALLY_APPROVED"}
ROLE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
PATH_PATTERN = re.compile(r"^(?:[a-z][a-z0-9+.-]*://[A-Za-z0-9._/-]+|[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._-]+)*)$")


class PersistencePolicyError(ValueError):
    pass


@dataclass(frozen=True)
class PersistencePolicy:
    policy_version: str
    artifact_type: Literal["registry_snapshot", "index_snapshot"]
    owner_role: str
    custodian_role: str
    storage_class: Literal["local_ephemeral", "local_encrypted", "managed_object_store", "external_worm"]
    allowed_root: str
    encryption_at_rest: bool
    access_mode: Literal["read_only", "append_only", "controlled_write"]
    retention_days: int
    backup_required: bool
    integrity_verification: Literal["sha256_manifest", "signed_manifest", "external_receipt"]
    raw_identity_allowed: bool = False
    clinical_data_allowed: bool = False
    external_authority: bool = False
    approval_state: Literal["UNAPPROVED", "SOFTWARE_VERIFIED", "EXTERNALLY_APPROVED"] = "UNAPPROVED"
    expires_at: str | None = None

    def validate(self) -> "PersistencePolicy":
        if self.policy_version != POLICY_VERSION:
            raise PersistencePolicyError("unsupported_policy_version")
        if self.artifact_type not in ARTIFACT_TYPES:
            raise PersistencePolicyError("unsupported_artifact_type")
        for role_name, role in (("owner_role", self.owner_role), ("custodian_role", self.custodian_role)):
            if not ROLE_PATTERN.fullmatch(role):
                raise PersistencePolicyError(f"{role_name}_invalid")
        if self.owner_role == self.custodian_role:
            raise PersistencePolicyError("owner_and_custodian_must_be_distinct")
        if self.storage_class not in STORAGE_CLASSES:
            raise PersistencePolicyError("unsupported_storage_class")
        if not PATH_PATTERN.fullmatch(self.allowed_root) or ".." in self.allowed_root.split("/"):
            raise PersistencePolicyError("allowed_root_invalid")
        if self.access_mode not in ACCESS_MODES:
            raise PersistencePolicyError("unsupported_access_mode")
        if not isinstance(self.retention_days, int) or isinstance(self.retention_days, bool) or self.retention_days < 0:
            raise PersistencePolicyError("retention_days_invalid")
        if self.storage_class == "local_ephemeral" and self.retention_days != 0:
            raise PersistencePolicyError("ephemeral_storage_requires_zero_retention")
        if self.storage_class != "local_ephemeral" and self.retention_days == 0:
            raise PersistencePolicyError("durable_storage_requires_positive_retention")
        if not isinstance(self.encryption_at_rest, bool):
            raise PersistencePolicyError("encryption_at_rest_must_be_boolean")
        if self.storage_class != "local_ephemeral" and self.encryption_at_rest is not True:
            raise PersistencePolicyError("durable_storage_requires_encryption")
        if not isinstance(self.backup_required, bool):
            raise PersistencePolicyError("backup_required_must_be_boolean")
        if self.storage_class != "local_ephemeral" and self.backup_required is not True:
            raise PersistencePolicyError("durable_storage_requires_backup")
        if self.integrity_verification not in INTEGRITY_METHODS:
            raise PersistencePolicyError("unsupported_integrity_verification")
        if self.raw_identity_allowed is not False:
            raise PersistencePolicyError("raw_identity_not_allowed")
        if self.clinical_data_allowed is not False:
            raise PersistencePolicyError("clinical_data_not_allowed_in_software_fixture")
        if self.external_authority is not False:
            raise PersistencePolicyError("external_authority_not_granted_locally")
        if self.approval_state not in APPROVAL_STATES:
            raise PersistencePolicyError("unsupported_approval_state")
        if self.approval_state == "EXTERNALLY_APPROVED":
            raise PersistencePolicyError("external_approval_not_verifiable_locally")
        if self.expires_at is not None:
            try:
                expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise PersistencePolicyError("expires_at_invalid") from exc
            if expiry.tzinfo is None:
                raise PersistencePolicyError("expires_at_must_be_timezone_aware")
        return self

    def software_verify(self) -> "PersistencePolicy":
        self.validate()
        return replace(self, approval_state="SOFTWARE_VERIFIED")

    def canonical_payload(self) -> dict[str, object]:
        self.validate()
        return asdict(self)

    def policy_hash(self) -> str:
        encoded = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def default_software_policy(artifact_type: Literal["registry_snapshot", "index_snapshot"]) -> PersistencePolicy:
    policy = PersistencePolicy(
        policy_version=POLICY_VERSION,
        artifact_type=artifact_type,
        owner_role="micro-rag-owner",
        custodian_role="micro-rag-custodian",
        storage_class="local_ephemeral",
        allowed_root="memory://p2-004",
        encryption_at_rest=False,
        access_mode="read_only",
        retention_days=0,
        backup_required=False,
        integrity_verification="sha256_manifest",
    )
    return policy.validate()


__all__ = [
    "APPROVAL_STATES",
    "ARTIFACT_TYPES",
    "PersistencePolicy",
    "PersistencePolicyError",
    "POLICY_VERSION",
    "default_software_policy",
]
