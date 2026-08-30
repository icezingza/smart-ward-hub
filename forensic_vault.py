"""Cryptographic helpers for tamper-evident forensic packages.

Private keys are loaded from an operator-controlled file and are never generated,
stored, or exported by the application. RSA-PSS signatures authenticate a block
hash; external key custody and trusted timestamps remain separate controls.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils


GENESIS_HASH = "0" * 64
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
SIGNATURE_ALGORITHM = "RSA-PSS-SHA256"


def canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
        default=str,
    )


def compute_block_hash(previous_hash: str, frozen_payload_json: str) -> str:
    if HASH_PATTERN.fullmatch(previous_hash) is None:
        raise ValueError("previous_hash must be a lowercase SHA-256 hex digest")
    material = f"{previous_hash}:{frozen_payload_json}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


@dataclass(frozen=True)
class ForensicSignature:
    algorithm: str
    signature_b64: str
    key_fingerprint: str


class RSAPSSForensicSigner:
    """Load and use a minimum RSA-2048 key without exposing private material."""

    def __init__(self, private_key: rsa.RSAPrivateKey) -> None:
        if private_key.key_size < 2048:
            raise ValueError("forensic RSA key must be at least 2048 bits")
        self._private_key = private_key
        public_der = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.key_fingerprint = hashlib.sha256(public_der).hexdigest()

    @classmethod
    def from_private_key_path(cls, path: str | Path) -> "RSAPSSForensicSigner":
        key_path = Path(path)
        private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise ValueError("forensic signing key must be an RSA private key")
        return cls(private_key)

    def sign_block_hash(self, block_hash: str) -> ForensicSignature:
        if HASH_PATTERN.fullmatch(block_hash) is None:
            raise ValueError("block_hash must be a lowercase SHA-256 hex digest")
        signature = self._private_key.sign(
            bytes.fromhex(block_hash),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            utils.Prehashed(hashes.SHA256()),
        )
        return ForensicSignature(
            algorithm=SIGNATURE_ALGORITHM,
            signature_b64=base64.b64encode(signature).decode("ascii"),
            key_fingerprint=self.key_fingerprint,
        )

    def verify_block_hash(self, block_hash: str, signature_b64: str) -> bool:
        if HASH_PATTERN.fullmatch(block_hash) is None:
            return False
        try:
            signature = base64.b64decode(signature_b64, validate=True)
            self._private_key.public_key().verify(
                signature,
                bytes.fromhex(block_hash),
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                utils.Prehashed(hashes.SHA256()),
            )
        except (InvalidSignature, ValueError):
            return False
        return True


def load_optional_signer(path: Path | None) -> RSAPSSForensicSigner | None:
    return None if path is None else RSAPSSForensicSigner.from_private_key_path(path)
