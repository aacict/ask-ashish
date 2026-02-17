"""
Chat Service
Orchestrates the RAG pipeline for question answering
"""
import logging
from typing import AsyncIterator, Optional
from uuid import UUID, uuid4

from src.core.rag.vector_store import get_vector_store_manager
from src.core.llm.client import get_llm_client
from src.models.schemas import ChatRequest, ChatResponse, SourceDocument

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling chat interactions with RAG"""
    
    def __init__(self) -> None:
        """Initialize chat service"""
        self.vector_store = get_vector_store_manager()
        self.llm_client = get_llm_client()
        self._conversation_store: dict[UUID, list[dict]] = {}
        
    def _calculate_confidence(
        self,
        sources: list[tuple[str, dict, float]],
        answer: str
    ) -> float:
        """
        Calculate confidence score based on retrieval scores and answer
        """
        if not sources:
            return 0.0
        
        # Average of top source scores
        avg_score = sum(score for _, _, score in sources[:3]) / min(len(sources), 3)
        
        # Normalize score (ChromaDB uses L2 distance, lower is better)
        # Convert to similarity score (inverse and normalize)
        confidence = max(0.0, min(1.0, 1.0 - (avg_score / 2.0)))
        
        # Penalize if answer indicates uncertainty
        uncertainty_phrases = [
            "i don't have",
            "i don't know",
            "not enough information",
            "cannot find",
            "unclear"
        ]
        
        answer_lower = answer.lower()
        if any(phrase in answer_lower for phrase in uncertainty_phrases):
            confidence *= 0.5
        
        return round(confidence, 2)
    
    async def ask_question(
        self,
        request: ChatRequest,
        conversation_history: Optional[list[dict]] = None
    ) -> ChatResponse:
        """
        Process a question and generate an answer using RAG
        """
        try:
            logger.info(f"Processing question: {request.question[:100]}...")
            
            # Retrieve relevant context
            sources = await self.vector_store.similarity_search(
                query=request.question,
                k=4
            )
            
            if not sources:
                logger.warning("No relevant sources found for question")
                return ChatResponse(
                    message_id=uuid4(),
                    conversation_id=request.conversation_id or uuid4(),
                    answer="I don't have enough information to answer that question. Could you ask something else about Ashish's background, skills, or experience?",
                    sources=[],
                    confidence=0.0,
                    model_used=self.llm_client.llm.model_name,
                    tokens_used=0
                )
            
            # Get or create conversation history
            conv_id = request.conversation_id or uuid4()
            history = conversation_history or self._conversation_store.get(conv_id, [])
            
            # Generate answer
            answer, metadata = await self.llm_client.generate_answer(
                question=request.question,
                context_sources=sources,
                conversation_history=history
            )
            
            # Update conversation history
            history.append({"role": "user", "content": request.question})
            history.append({"role": "assistant", "content": answer})
            self._conversation_store[conv_id] = history[-10:]  # Keep last 10 messages
            
            # Format sources for response
            source_docs = [
                SourceDocument(
                    content=content,
                    metadata=metadata,
                    relevance_score=round(1.0 - (score / 2.0), 2)  # Normalize score
                )
                for content, metadata, score in sources
            ]
            
            # Calculate confidence
            confidence = self._calculate_confidence(sources, answer)
            
            return ChatResponse(
                message_id=uuid4(),
                conversation_id=conv_id,
                answer=answer,
                sources=source_docs,
                confidence=confidence,
                model_used=metadata["model"],
                tokens_used=metadata["tokens_used"]
            )
            
        except Exception as e:
            logger.error(f"Error processing question: {e}", exc_info=True)
            raise
    
    async def ask_question_stream(
        self,
        request: ChatRequest,
        conversation_history: Optional[list[dict]] = None
    ) -> AsyncIterator[str]:
        """
        Process a question and stream the answer
        """
        try:
            logger.info(f"Streaming answer for question: {request.question[:100]}...")
            
            # Retrieve relevant context
            sources = await self.vector_store.similarity_search(
                query=request.question,
                k=4
            )
            
            if not sources:
                yield "I don't have enough information to answer that question. Could you ask something else about Ashish's background, skills, or experience?"
                return
            
            # Get conversation history
            conv_id = request.conversation_id or uuid4()
            history = conversation_history or self._conversation_store.get(conv_id, [])
            
            # Stream answer
            full_answer = ""
            async for chunk in self.llm_client.generate_answer_stream(
                question=request.question,
                context_sources=sources,
                conversation_history=history
            ):
                full_answer += chunk
                yield chunk
            
            # Update conversation history
            history.append({"role": "user", "content": request.question})
            history.append({"role": "assistant", "content": full_answer})
            self._conversation_store[conv_id] = history[-10:]
            
        except Exception as e:
            logger.error(f"Error streaming answer: {e}", exc_info=True)
            raise
    
    async def get_conversation_summary(self, conversation_id: UUID) -> Optional[str]:
        """
        Get a summary of a conversation
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Summary text or None
        """
        history = self._conversation_store.get(conversation_id)
        if not history:
            return None
        
        try:
            summary = await self.llm_client.summarize_conversation(history)
            return summary
        except Exception as e:
            logger.error(f"Failed to summarize conversation: {e}")
            return None
    
    def clear_conversation(self, conversation_id: UUID) -> bool:
        """
        Clear a conversation from history
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            True if conversation was found and cleared
        """
        if conversation_id in self._conversation_store:
            del self._conversation_store[conversation_id]
            return True
        return False
    
    def get_conversation_count(self) -> int:
        """Get number of active conversations"""
        return len(self._conversation_store)


# Singleton instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create chat service singleton"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service