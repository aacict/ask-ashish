import hashlib
import logging
from typing import Optional

import tiktoken
from langchain_openai import OpenAIEmbeddings
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from app.config.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingsManager:
    """Manages embeddings generation with caching and retries"""
    
    def __init__(self) -> None:
        """Initialize embeddings manager"""
        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.openai_api_key,
            chunk_size=1000,  # Batch size for API calls
        )
        self.encoding = tiktoken.encoding_for_model(settings.embedding_model)
        self._cache: dict[str, list[float]] = {}
        
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        return hashlib.sha256(text.encode()).hexdigest()
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoding.encode(text))
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def embed_text(self, text: str, use_cache: bool = True) -> list[float]:
        """
        Generate embeddings for text with caching and retry logic
        """
        if not text.strip():
            raise ValueError("Cannot embed empty text")
        
        # Check cache
        cache_key = self._get_cache_key(text)
        if use_cache and cache_key in self._cache:
            logger.debug(f"Cache hit for text: {text[:50]}...")
            return self._cache[cache_key]
        
        try:
            # Generate embedding
            logger.debug(f"Generating embedding for text: {text[:50]}...")
            embedding = await self.embeddings.aembed_query(text)
            
            # Validate embedding
            if not embedding or len(embedding) != settings.embedding_dimension:
                raise ValueError(
                    f"Invalid embedding dimension: {len(embedding) if embedding else 0}"
                )
            
            # Cache result
            if use_cache:
                self._cache[cache_key] = embedding
                
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def embed_documents(
        self,
        texts: list[str],
        use_cache: bool = True
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple documents
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        embeddings = []
        uncached_texts = []
        uncached_indices = []
        
        # Check cache first
        for idx, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            if use_cache and cache_key in self._cache:
                embeddings.append(self._cache[cache_key])
            else:
                embeddings.append(None)
                uncached_texts.append(text)
                uncached_indices.append(idx)
        
        # Generate embeddings for uncached texts
        if uncached_texts:
            try:
                logger.info(f"Generating embeddings for {len(uncached_texts)} documents")
                new_embeddings = await self.embeddings.aembed_documents(uncached_texts)
                
                # Update cache and results
                for idx, embedding in zip(uncached_indices, new_embeddings):
                    embeddings[idx] = embedding
                    if use_cache:
                        cache_key = self._get_cache_key(texts[idx])
                        self._cache[cache_key] = embedding
                        
            except Exception as e:
                logger.error(f"Failed to generate batch embeddings: {e}")
                raise
        
        return embeddings
    
    def clear_cache(self) -> None:
        """Clear embedding cache"""
        self._cache.clear()
        logger.info("Embedding cache cleared")
    
    def get_cache_size(self) -> int:
        """Get number of cached embeddings"""
        return len(self._cache)


# Singleton instance
_embeddings_manager: Optional[EmbeddingsManager] = None


def get_embeddings_manager() -> EmbeddingsManager:
    """Get or create embeddings manager singleton"""
    global _embeddings_manager
    if _embeddings_manager is None:
        _embeddings_manager = EmbeddingsManager()
    return _embeddings_manager