"""
Main FastAPI Application
"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from scripts import ingest_data
from slowapi.errors import RateLimitExceeded

from src.config.settings import get_settings
from src.api.routes import chat, health
from src.core.security.auth import limiter, rate_limit_exceeded_handler
from src.models.schemas import ErrorResponse
settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    Runs on startup and shutdown
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Initialize components
    try:
        from src.core.rag.vector_store import get_vector_store_manager
        from src.core.llm.client import get_llm_client
        
        vector_store = get_vector_store_manager()
        stats = await vector_store.get_collection_stats()
        logger.info(f"Vector store initialized: {stats.get('count', 0)} documents")

        if stats.get("count", 0) == 0:
            logger.info("Vector store empty. Starting ingestion...")
            await ingest_data("data/knowledge_base")
            logger.info("Ingestion complete.")
        else:
            logger.info(f"Vector store already initialized with {stats['count']} chunks.")
        
        llm_client = get_llm_client()
        logger.info(f"LLM client initialized: {settings.openai_model}")
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered assistant to answer questions about Ashish using RAG",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# Add rate limiter state
app.state.limiter = limiter


# Middleware
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Exception handlers
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceptions"""
    return rate_limit_exceeded_handler(request, exc)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="An unexpected error occurred",
            detail=str(exc) if settings.debug else None
        ).model_dump()
    )


# Routes
app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(chat.router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs" if settings.debug else "disabled",
    }


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    logger.info(f"{request.method} {request.url.path}")
    
    response = await call_next(request)
    
    logger.info(f"{request.method} {request.url.path} - {response.status_code}")
    
    return response


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )