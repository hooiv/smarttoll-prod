import logging
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from app.config import settings

log = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=True)


async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Dependency to verify the provided API key.

    Uses constant-time comparison to prevent timing-based side-channel attacks.
    """
    configured_key = settings.SERVICE_API_KEY
    if not configured_key:
        log.error("SERVICE_API_KEY is not configured — all API key checks will fail.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key authentication is not configured on this server.",
        )
    if secrets.compare_digest(api_key, configured_key):
        log.debug("Valid API key received.")
        return api_key
    log.warning(f"Invalid API key attempt: '{api_key[:4]}...'")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key",
    )