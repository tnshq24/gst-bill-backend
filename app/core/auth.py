"""JWT auth helpers for API endpoints."""

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict

from fastapi import Header, HTTPException

from app.core.config import settings


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _verify_signature(signing_input: bytes, signature_b64: str, secret: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual = _b64url_decode(signature_b64)
    return hmac.compare_digest(expected, actual)


def _validate_claims(payload: Dict[str, Any]) -> None:
    now = int(time.time())
    exp = payload.get("exp")
    if exp is None or not isinstance(exp, int):
        raise HTTPException(status_code=401, detail="Token missing exp")
    if exp < now:
        raise HTTPException(status_code=401, detail="Token expired")

    iss = payload.get("iss")
    if settings.jwt_issuer and iss != settings.jwt_issuer:
        raise HTTPException(status_code=401, detail="Invalid issuer")

    aud = payload.get("aud")
    if settings.jwt_audience:
        if isinstance(aud, str):
            valid_aud = aud == settings.jwt_audience
        elif isinstance(aud, list):
            valid_aud = settings.jwt_audience in aud
        else:
            valid_aud = False
        if not valid_aud:
            raise HTTPException(status_code=401, detail="Invalid audience")


def decode_jwt(token: str) -> Dict[str, Any]:
    if not settings.jwt_secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")

    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Invalid token format")

    header_b64, payload_b64, signature_b64 = parts
    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token encoding")

    if header.get("alg") != "HS256":
        raise HTTPException(status_code=401, detail="Unsupported token algorithm")

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    if not _verify_signature(signing_input, signature_b64, settings.jwt_secret):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    _validate_claims(payload)
    return payload


def require_jwt(authorization: str = Header(..., alias="Authorization")) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    return decode_jwt(token)
