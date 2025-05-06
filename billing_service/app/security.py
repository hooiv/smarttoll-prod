import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

log = logging.getLogger(__name__)

# --- Basic API Key Authentication ---
# WARNING: For production, store API keys securely and consider OAuth2/OIDC.
VALID_API_KEYS = {settings.SERVICE_API_KEY} if hasattr(settings, 'SERVICE_API_KEY') else {"supersecretapikey123"}

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=True)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Dependency to verify the provided API key."""
    if api_key in VALID_API_KEYS:
        log.debug("Valid API key received.")
        return api_key
    log.warning(f"Invalid API key received: '{api_key[:5]}...'")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key",
    )