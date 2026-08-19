import secrets
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from oidc import OIDCVerifier, scopes_from_claims


bearer_scheme = HTTPBearer(auto_error=False)
TOKENS = settings.auth_tokens
OIDC_VERIFIER = OIDCVerifier() if settings.auth_mode == "oidc" else None


def _missing_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Bearer token required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _static_auth(credentials: HTTPAuthorizationCredentials | None) -> dict[str, Any]:
    if not TOKENS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _missing_credentials()
    matched_token = next(
        (
            token
            for token in TOKENS
            if secrets.compare_digest(token, credentials.credentials)
        ),
        None,
    )
    if matched_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"token_subject": "configured-service", "scopes": sorted(TOKENS[matched_token])}


def _oidc_auth(credentials: HTTPAuthorizationCredentials | None) -> dict[str, Any]:
    if OIDC_VERIFIER is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC authentication is not configured.",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _missing_credentials()
    claims = OIDC_VERIFIER.verify(credentials.credentials)
    return {
        "token_subject": str(claims["sub"]),
        "scopes": sorted(scopes_from_claims(claims)),
        "issuer": claims.get("iss"),
    }


def require_scope(required_scope: str):
    def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> dict[str, Any]:
        if settings.auth_mode == "oidc":
            identity = _oidc_auth(credentials)
        elif settings.auth_mode == "static":
            identity = _static_auth(credentials)
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unsupported authentication mode.",
            )
        scopes = set(identity.get("scopes", []))
        if required_scope not in scopes and "admin" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing scope: {required_scope}",
            )
        return identity

    return dependency
