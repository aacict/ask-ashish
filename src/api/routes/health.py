"""
Health Check and Admin Routes
"""
import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from src.models.schemas import HealthResponse
from src.config.settings import get_settings
from src.core.rag.vector_store import get_vector_store_manager
from src.core.security.auth import verify_api_key
settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])

# Track startup time for uptime calculation
_startup_time = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check the health status of the application and its dependencies"
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint
    
    Returns the health status of the application and its components
    """
    checks = {}
    
    # Check vector store
    try:
        vector_store = get_vector_store_manager()
        stats = await vector_store.get_collection_stats()
        checks["vector_store"] = "error" not in stats
    except Exception as e:
        logger.error(f"Vector store health check failed: {e}")
        checks["vector_store"] = False
    
    # Check OpenAI connectivity (simple check)
    try:
        from src.core.llm.client import get_llm_client
        llm_client = get_llm_client()
        checks["llm"] = llm_client.llm is not None
    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        checks["llm"] = False
    
    # Determine overall status
    all_healthy = all(checks.values())
    status_str = "healthy" if all_healthy else "degraded"
    
    if not any(checks.values()):
        status_str = "unhealthy"
    
    return HealthResponse(
        status=status_str,
        version=settings.app_version,
        environment=settings.environment,
        checks=checks,
        timestamp=datetime.utcnow()
    )


@router.get(
    "/health/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Simple liveness check for Kubernetes/container orchestration"
)
async def liveness_probe() -> dict:
    """Liveness probe - returns 200 if application is running"""
    return {"status": "alive"}


@router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Readiness check - returns 200 if application is ready to serve traffic"
)
async def readiness_probe() -> dict:
    """Readiness probe - checks if app can handle requests"""
    try:
        # Quick check of critical components
        vector_store = get_vector_store_manager()
        stats = await vector_store.get_collection_stats()
        
        if "error" in stats:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Vector store not ready"
            )
        
        return {"status": "ready"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application not ready"
        )

@router.get(
    "/admin/vector-store/stats",
    status_code=status.HTTP_200_OK,
    summary="Vector store statistics",
    description="Get detailed statistics about the vector store (requires API key)"
)
async def get_vector_store_stats(
    _: str = Depends(verify_api_key)
) -> dict:
    """Get vector store statistics"""
    try:
        vector_store = get_vector_store_manager()
        stats = await vector_store.get_collection_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting vector store stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get vector store statistics"
        )


@router.post(
    "/admin/vector-store/reset",
    status_code=status.HTTP_200_OK,
    summary="Reset vector store",
    description="Delete all documents from vector store (requires API key, use with caution!)"
)
async def reset_vector_store(
    confirm: bool = False,
    _: str = Depends(verify_api_key)
) -> dict:
    """
    Reset vector store (requires confirmation)
    
    This will delete ALL documents from the vector store!
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must set confirm=true to reset vector store"
        )
    
    try:
        vector_store = get_vector_store_manager()
        await vector_store.reset_collection()
        
        logger.warning("Vector store has been reset")
        return {
            "status": "success",
            "message": "Vector store has been reset"
        }
        
    except Exception as e:
        logger.error(f"Error resetting vector store: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset vector store"
        )