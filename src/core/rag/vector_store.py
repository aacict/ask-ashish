import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VectorStoreManager:
    """
    Manages our vector database (ChromaDB)
    """
    
    def __init__(self):
        """Initialize the vector store"""
        # Create directory if it doesn't exist
        self.persist_directory = Path(settings.chroma_persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # Initialize OpenAI embeddings
        # This converts text → vectors
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.openai_api_key
        )
        
        # Text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        
        self._vector_store = None
    
    def _get_vector_store(self) -> Chroma:
        """
        Get or create the vector store (lazy loading)
        """
        if self._vector_store is None:
            self._vector_store = Chroma(
                client=self.client,
                collection_name="ashish_knowledge",
                embedding_function=self.embeddings,
            )
        return self._vector_store
    
    async def add_documents(
        self,
        documents: list[str],
        metadatas: Optional[list[dict]] = None
    ) -> list[str]:
        """
        Add documents to the vector store    
        Returns:
            List of document IDs
        """
        # Step 1: Split documents into chunks
        all_chunks = []
        all_metadatas = []
        
        for idx, doc in enumerate(documents):
            chunks = self.text_splitter.split_text(doc)
            all_chunks.extend(chunks)
            
            # Add metadata to each chunk
            base_metadata = metadatas[idx] if metadatas else {}
            for chunk_idx in range(len(chunks)):
                chunk_metadata = {
                    **base_metadata,
                    "chunk_index": chunk_idx,
                    "total_chunks": len(chunks),
                }
                all_metadatas.append(chunk_metadata)
        
        logger.info(f"Adding {len(all_chunks)} chunks to vector store")
        
        # Step 2: Add to vector store
        # This will automatically create embeddings
        vector_store = self._get_vector_store()
        doc_ids = vector_store.add_texts(
            texts=all_chunks,
            metadatas=all_metadatas
        )
        
        logger.info(f"Successfully added {len(doc_ids)} chunks")
        return doc_ids
    
    async def similarity_search(
        self,
        query: str,
        k: int = 4
    ) -> list[tuple[str, dict, float]]:
        """
        Search for similar documents
        
        Args:
            query: The search query
            k: Number of results to return
            
        Returns:
            List of (content, metadata, score) tuples
        """
        vector_store = self._get_vector_store()
        
        # Perform similarity search
        # ChromaDB converts the query to vector and finds nearest neighbors
        results = vector_store.similarity_search_with_score(
            query=query,
            k=k
        )
        
        # Format results
        formatted = [
            (doc.page_content, doc.metadata, score)
            for doc, score in results
        ]
        
        logger.info(f"Found {len(formatted)} results for query: {query[:50]}")
        return formatted
    
    async def get_collection_stats(self) -> dict:
        """Get statistics about the collection"""
        try:
            collection = self.client.get_collection("ashish_knowledge")
            return {
                "name": collection.name,
                "count": collection.count(),
            }
        except Exception as e:
            return {"error": str(e)}


# Singleton pattern - only create one instance
_vector_store_manager = None

def get_vector_store_manager() -> VectorStoreManager:
    """Get or create the vector store manager"""
    global _vector_store_manager
    if _vector_store_manager is None:
        _vector_store_manager = VectorStoreManager()
    return _vector_store_manager