from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application Info
    app_name: str = "Ask Ashish AI"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"  # development, staging, production
    
    # Security - MUST be set in .env
    secret_key: str  # For JWT tokens
    api_key: str = None  # Optional API key for authentication
    
    # OpenAI
    openai_api_key: str  # Your OpenAI API key
    openai_model: str = "gpt-4-turbo-preview"
    embedding_model: str = "text-embedding-3-small"  # OpenAI embedding model
    
    # Vector Store
    chroma_persist_directory: str = "/src/data/chroma"
    
    allowed_origins: str = "*"  # CORS allowed origins

    # RAG Settings
    chunk_size: int = 1000  # Size of text chunks
    chunk_overlap: int = 200  # Overlap between chunks
    retrieval_top_k: int = 4  # Number of documents to retrieve

    redis_url: str   # Redis URL for rate limiting
    rate_limit_enabled: bool = True  # Enable rate limiting
    rate_limit_per_minute: int = 60  # Max requests per minute

    log_level: str = "INFO"  # Logging level
    debug: bool = False  # Debug mode
    
    class Config:
        env_file = ".env"  # Load from .env file

@lru_cache()  # Cache the settings (singleton pattern)
def get_settings() -> Settings:
    return Settings()