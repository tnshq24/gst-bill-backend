"""API routes for Azure Speech and Avatar relay tokens."""

from typing import Any, Dict
import asyncio
import requests
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_jwt
from app.core.config import settings

router = APIRouter(tags=["avatar_tokens"])


def _ensure_speech_config() -> None:
    if not settings.speech_key or not settings.speech_region:
        raise HTTPException(
            status_code=500,
            detail="Speech configuration missing: set SPEECH_KEY and SPEECH_REGION",
        )


def _get_speech_token_sync() -> Dict[str, Any]:
    _ensure_speech_config()
    endpoint = settings.speech_token_endpoint or (
        f"https://{settings.speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": settings.speech_key,
        "Ocp-Apim-Subscription-Region": settings.speech_region,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    response = requests.post(
        endpoint,
        headers=headers,
        data="",
        timeout=settings.request_timeout_secs,
    )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to fetch speech token: {response.text}",
        )
    return {
        "token": response.text,
        "region": settings.speech_region,
    }


def _normalize_ice_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Enforce a stable response contract for frontend usage.
    urls = payload.get("Urls") or payload.get("urls")
    username = payload.get("Username") or payload.get("username") or payload.get("userName")
    password = payload.get("Password") or payload.get("password") or payload.get("credential")

    if (not urls or not username or not password) and isinstance(payload.get("iceServers"), list):
        first_server = payload["iceServers"][0] if payload["iceServers"] else {}
        urls = urls or first_server.get("urls")
        username = username or first_server.get("username")
        password = password or first_server.get("credential")

    if not urls or not username or not password:
        raise HTTPException(
            status_code=502,
            detail=f"Unexpected ICE token payload format: {payload}",
        )

    if isinstance(urls, str):
        urls = [urls]

    return {
        "Urls": urls,
        "Username": username,
        "Password": password,
    }


def _get_ice_token_sync() -> Dict[str, Any]:
    _ensure_speech_config()
    endpoint = settings.speech_ice_endpoint or (
        f"https://{settings.speech_region}.tts.speech.microsoft.com/cognitiveservices/avatar/relay/token/v1"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": settings.speech_key,
        "Ocp-Apim-Subscription-Region": settings.speech_region,
    }

    response = requests.get(
        endpoint,
        headers=headers,
        timeout=settings.request_timeout_secs,
    )
    if response.status_code in (404, 405):
        # Some deployments expect POST for this endpoint.
        response = requests.post(
            endpoint,
            headers=headers,
            timeout=settings.request_timeout_secs,
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to fetch ICE token: {response.text}",
        )
    return _normalize_ice_payload(response.json())


@router.get("/token")
async def get_speech_token(_auth: Dict[str, Any] = Depends(require_jwt)) -> Dict[str, Any]:
    """Return short-lived Azure Speech token for frontend avatar/speech usage."""
    return await asyncio.to_thread(_get_speech_token_sync)


@router.get("/ice-token")
async def get_avatar_ice_token(_auth: Dict[str, Any] = Depends(require_jwt)) -> Dict[str, Any]:
    """Return short-lived ICE relay credentials for avatar WebRTC."""
    return await asyncio.to_thread(_get_ice_token_sync)
