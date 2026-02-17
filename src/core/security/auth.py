"""
Security Middleware
Handles authentication, rate limiting, and security headers
"""
import logging
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.config.settings import get_settings
settings = get_settings()

logger = logging.getLogger(__name__)

# API Key Security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Verify API key if configured
    """
    # Skip validation if no API key is configured
    if not settings.api_key:
        return "not-required"
    
    if not api_key:
        logger.warning("Missing API key in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if api_key != settings.api_key:
        logger.warning("Invalid API key attempted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return api_key


# Rate Limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url if settings.rate_limit_enabled else None,
    enabled=settings.rate_limit_enabled,
)


def get_rate_limit_string() -> str:
    """Get rate limit string for decorator"""
    return f"{settings.rate_limit_per_minute}/minute"


# CORS Headers
def get_cors_headers() -> dict[str, str]:
    """Get CORS headers"""
    return {
        "Access-Control-Allow-Origin": ", ".join(settings.allowed_origins),
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key, Authorization",
        "Access-Control-Max-Age": "3600",
    }


# Security Headers
def get_security_headers() -> dict[str, str]:
    """Get security headers"""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
    }


def rate_limit_exceeded_handler(request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded"""
    logger.warning(f"Rate limit exceeded for {get_remote_address(request)}")
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Rate limit exceeded: {exc.detail}",
        headers={"Retry-After": "60"}
    )