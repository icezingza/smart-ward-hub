import os
import hashlib
import secrets
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from oidc import OIDCVerifier, scopes_from_claims


bearer_scheme = HTTPBearer(auto_error=False)
TOKENS = settings.auth_tokens
TOKEN_HASHES = settings.auth_token_hashes
OIDC_VERIFIER = OIDCVerifier() if settings.auth_mode == "oidc" else None

# AegisGrid Security Engine Integration
AEGIS_TOKEN_MANAGER = None

_aegis_keys_configured = bool(
    os.getenv("NAMO_JWT_PUBLIC_KEY") or os.getenv("SW_JWT_PUBLIC_KEY")
)

if settings.auth_mode == "aegis" or _aegis_keys_configured:
    try:
        import aegisgrid
        from aegisgrid import TokenManager, AuthLevel

        pub_key = os.getenv("NAMO_JWT_PUBLIC_KEY") or os.getenv("SW_JWT_PUBLIC_KEY")
        priv_key = os.getenv("NAMO_JWT_PRIVATE_KEY") or os.getenv("SW_JWT_PRIVATE_KEY")

        if not pub_key:
            raise RuntimeError("Aegis authentication is configured but public key is missing.")

        AEGIS_TOKEN_MANAGER = TokenManager(
            public_key=pub_key,
            private_key=priv_key,
            issuer="smart-ward-hub",
            audience="smart-ward-pda",
        )
    except ImportError as exc:
        raise RuntimeError("aegisgrid library is required but not installed.") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize Aegis token manager: {exc}") from exc


def _missing_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Bearer token required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _static_auth(credentials: HTTPAuthorizationCredentials | None) -> dict[str, Any]:
    if not TOKENS and not TOKEN_HASHES and AEGIS_TOKEN_MANAGER is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _missing_credentials()

    raw_cred = credentials.credentials

    # 1. AegisGrid Ed25519 Token Verification (if JWT formatted)
    if AEGIS_TOKEN_MANAGER is not None and "." in raw_cred and raw_cred.count(".") == 2:
        claims = AEGIS_TOKEN_MANAGER.verify_token(raw_cred)
        if claims is not None:
            auth_lvl = claims.get("auth_level", 1)
            scopes = ["telemetry:read", "pairing:write"]
            if auth_lvl >= 2:
                scopes.append("admin")
            return {
                "token_subject": claims.get("user_id", "aegis-authenticated-client"),
                "scopes": scopes,
                "issuer": claims.get("iss", "aegisgrid"),
                "auth_engine": "aegisgrid-eddsa",
            }
    
    # 2. Check plain tokens if configured
    matched_token = next(
        (
            token
            for token in TOKENS
            if secrets.compare_digest(token, raw_cred)
        ),
        None,
    )
    if matched_token is not None:
        return {"token_subject": "configured-service", "scopes": sorted(TOKENS[matched_token])}

    # 3. Check hashed tokens
    if TOKEN_HASHES:
        token_digest = hashlib.sha256(raw_cred.encode("utf-8")).hexdigest().lower()
        matched_hash = next(
            (
                h
                for h in TOKEN_HASHES
                if secrets.compare_digest(h, token_digest)
            ),
            None,
        )
        if matched_hash is not None:
            return {"token_subject": "configured-service", "scopes": sorted(TOKEN_HASHES[matched_hash])}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


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


def verify_raw_token(token_str: str | None, required_scope: str = "telemetry:read") -> bool:
    """Verify raw token string for WebSocket handshakes and non-standard HTTP transports."""
    if not token_str:
        return False
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_str)
    try:
        if settings.auth_mode == "oidc":
            identity = _oidc_auth(creds)
        elif settings.auth_mode == "static":
            identity = _static_auth(creds)
        else:
            return False
        scopes = set(identity.get("scopes", []))
        return required_scope in scopes or "admin" in scopes
    except Exception:
        return False
