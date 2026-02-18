import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.rag.vector_store import get_vector_store_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def load_markdown_files(directory: Path) -> list[tuple[str, dict]]:
    """
    Load all .md files from a directory
    
    Returns:
        List of (content, metadata) tuples
    """
    documents = []
    
    if not directory.exists():
        logger.error(f"Directory not found: {directory}")
        return documents
    
    # Find all markdown files
    for file_path in directory.glob("**/*.md"):
        try:
            # Read file content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Create metadata
            metadata = {
                "source": file_path.name,
                "path": str(file_path.relative_to(directory)),
                "type": "markdown"
            }
            
            documents.append((content, metadata))
            logger.info(f"✅ Loaded: {file_path.name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load {file_path}: {e}")
    
    return documents


async def ingest_data(data_dir: str = "./data/knowledge_base"):
    """
    Main ingestion function
    
    Steps:
    1. Load markdown files
    2. Split into chunks
    3. Create embeddings
    4. Store in vector database
    """
    try:
        vector_store = get_vector_store_manager()
        
        # Load documents
        data_path = Path(data_dir)
        logger.info(f"📂 Loading documents from: {data_path}")
        
        doc_data = await load_markdown_files(data_path)
        
        if not doc_data:
            logger.warning("⚠️  No documents found!")
            return
        
        # Separate content and metadata
        documents = [content for content, _ in doc_data]
        metadatas = [metadata for _, metadata in doc_data]
        
        # Add to vector store
        logger.info(f"💾 Adding {len(documents)} documents to vector store...")
        doc_ids = await vector_store.add_documents(
            documents=documents,
            metadatas=metadatas
        )
        
        logger.info(f"✅ Successfully added {len(doc_ids)} document chunks")
        
        # Show stats
        stats = await vector_store.get_collection_stats()
        logger.info(f"📊 Collection now has {stats.get('count', 0)} total chunks")
        
    except Exception as e:
        logger.error(f"❌ Ingestion failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest knowledge base")
    parser.add_argument(
        "--data-dir",
        default="./data/knowledge_base",
        help="Directory with markdown files"
    )
    
    args = parser.parse_args()
    
    # Run ingestion
    asyncio.run(ingest_data(args.data_dir))