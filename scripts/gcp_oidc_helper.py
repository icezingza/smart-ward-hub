#!/usr/bin/env python3
"""
gcp_oidc_helper.py — GCP Identity Platform / Firebase OIDC Token Utility
========================================================================
Developer utility for interacting with GCP Identity Platform (Firebase Auth)
to acquire and validate OIDC tokens during Smart Ward Hub testing.

Usage:
    # 1. Exchange custom JWT for GCP OIDC Token
    python scripts/gcp_oidc_helper.py get-token --custom-token <jwt> --api-key <gcp_api_key>
    
    # 2. Login with Email/Password
    python scripts/gcp_oidc_helper.py login --email user@test.local --password testpass --api-key <gcp_api_key>

    # 3. Decode and view token claims locally
    python scripts/gcp_oidc_helper.py decode --token <oidc_jwt>
"""
import argparse
import json
import sys
import base64
from urllib import request, error


def decode_token(token: str) -> None:
    """Decode and print JWT claims without signature verification (for debugging only)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format (must have 3 parts).")
        
        # Add padding if needed
        header_b64 = parts[0] + "=" * (-len(parts[0]) % 4)
        claims_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        
        header = json.loads(base64.urlsafe_b64decode(header_b64).decode("utf-8"))
        claims = json.loads(base64.urlsafe_b64decode(claims_b64).decode("utf-8"))
        
        print("\n--- Header ---")
        print(json.dumps(header, indent=2))
        print("\n--- Claims ---")
        print(json.dumps(claims, indent=2))
        print("\nNote: Signature NOT verified locally. Use Hub API to verify.")
    except Exception as e:
        print(f"[ERROR] Failed to decode token: {e}", file=sys.stderr)
        sys.exit(1)


def exchange_custom_token(custom_token: str, api_key: str) -> None:
    """Exchange a custom token (e.g., from AegisGrid) for a GCP Identity token."""
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={api_key}"
    payload = json.dumps({"token": custom_token, "returnSecureToken": True}).encode("utf-8")
    _make_identity_request(url, payload)


def login_email_password(email: str, password: str, api_key: str) -> None:
    """Login to GCP Identity Platform using Email and Password."""
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    payload = json.dumps({"email": email, "password": password, "returnSecureToken": True}).encode("utf-8")
    _make_identity_request(url, payload)


def _make_identity_request(url: str, payload: bytes) -> None:
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            print("\n[SUCCESS] Retrieved OIDC Token")
            print("="*60)
            print(data.get("idToken"))
            print("="*60)
            print(f"Expires In: {data.get('expiresIn')} seconds")
            print(f"User ID: {data.get('localId')}")
    except error.HTTPError as e:
        print(f"\n[ERROR] GCP API Request Failed: HTTP {e.code}", file=sys.stderr)
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            print(json.dumps(err_data, indent=2), file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Network error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="GCP Identity Platform OIDC Utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # get-token
    parser_custom = subparsers.add_parser("get-token", help="Exchange custom token")
    parser_custom.add_argument("--custom-token", required=True)
    parser_custom.add_argument("--api-key", required=True, help="GCP Public API Key")

    # login
    parser_login = subparsers.add_parser("login", help="Login via Email/Password")
    parser_login.add_argument("--email", required=True)
    parser_login.add_argument("--password", required=True)
    parser_login.add_argument("--api-key", required=True, help="GCP Public API Key")

    # decode
    parser_decode = subparsers.add_parser("decode", help="Decode JWT payload")
    parser_decode.add_argument("--token", required=True, help="OIDC JWT Token")

    args = parser.parse_args()

    if args.command == "decode":
        decode_token(args.token)
    elif args.command == "get-token":
        exchange_custom_token(args.custom_token, args.api_key)
    elif args.command == "login":
        login_email_password(args.email, args.password, args.api_key)


if __name__ == "__main__":
    main()
