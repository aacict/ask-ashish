from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application Info
    app_name: str = "Ask Ashish AI"
    environment: str = "development"  # development, staging, production
    
    # Security - MUST be set in .env
    secret_key: str  # For JWT tokens
    api_key: str = None  # Optional API key for authentication
    
    # OpenAI
    openai_api_key: str  # Your OpenAI API key
    openai_model: str = "gpt-4-turbo-preview"
    
    # Vector Store
    chroma_persist_directory: str = "./data/chroma"
    
    # RAG Settings
    chunk_size: int = 1000  # Size of text chunks
    chunk_overlap: int = 200  # Overlap between chunks
    retrieval_top_k: int = 4  # Number of documents to retrieve
    
    class Config:
        env_file = ".env"  # Load from .env file

@lru_cache()  # Cache the settings (singleton pattern)
def get_settings() -> Settings:
    return Settings()