from __future__ import annotations

from typing import Any

import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError
from jwt.jwks_client import PyJWKClient

from config import settings


class OIDCVerifier:
    def __init__(self) -> None:
        if not settings.oidc_issuer or not settings.oidc_audience or not settings.oidc_jwks_url:
            raise RuntimeError(
                "OIDC mode requires SW_OIDC_ISSUER, SW_OIDC_AUDIENCE, and SW_OIDC_JWKS_URL"
            )
        self.issuer = settings.oidc_issuer
        self.audience = settings.oidc_audience
        self.algorithms = settings.oidc_algorithms
        self.client = PyJWKClient(settings.oidc_jwks_url, cache_jwk_set=True)

    def verify(self, token: str) -> dict[str, Any]:
        try:
            signing_key = self.client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except (InvalidTokenError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid OIDC access token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        return claims


def scopes_from_claims(claims: dict[str, Any]) -> set[str]:
    scope_claim = claims.get("scope", claims.get("scp", []))
    if isinstance(scope_claim, str):
        return {item for item in scope_claim.split() if item}
    if isinstance(scope_claim, list):
        return {str(item) for item in scope_claim}
    return set()
