"""API routes for auth/token endpoints."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.dto import TokenRequest, TokenResponse

router = APIRouter(prefix="/url", tags=["auth"])


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign_hs256(message: bytes, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url(signature)


def _create_jwt(payload: Dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = _sign_hs256(signing_input, secret)
    return f"{header_b64}.{payload_b64}.{signature}"


@router.post("/token", response_model=TokenResponse)
async def issue_token(request: TokenRequest) -> TokenResponse:
    """Issue a JWT token for API authentication."""
    if not settings.api_client_id or not settings.api_client_secret:
        raise HTTPException(
            status_code=500,
            detail="Token endpoint not configured",
        )
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=500,
            detail="JWT secret not configured",
        )

    if (
        request.client_id != settings.api_client_id
        or request.client_secret != settings.api_client_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    now = int(time.time())
    expires_in = int(settings.jwt_exp_minutes) * 60
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + expires_in,
        "sub": request.subject or request.client_id,
        "jti": secrets.token_urlsafe(16),
        "scopes": request.scopes or [],
    }

    token = _create_jwt(payload, settings.jwt_secret)
    return TokenResponse(access_token=token, expires_in=expires_in)
