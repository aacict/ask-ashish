"""
app/core/llm/client.py
"""
import logging
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMClient:
    """
    Client for interacting with OpenAI's language models
    """
    # This is the instruction for the AI
    SYSTEM_PROMPT = """You are an AI assistant that answers questions about Ashish.
            Your rules:
            1. Answer ONLY using the provided context
            2. If the context doesn't have the answer, say "I don't have that information"
            3. Be conversational and friendly
            4. Keep answers concise but informative
            5. Cite which part of the context you're using

            Remember: Be helpful, accurate, and honest."""
    
    def __init__(self):
        """Initialize the LLM client"""
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.7,  # 0 = deterministic, 1 = creative
            openai_api_key=settings.openai_api_key,
        )
    
    def _format_context(
        self,
        sources: list[tuple[str, dict, float]]
    ) -> str:
        """
        Format retrieved documents into a context string
        """
        if not sources:
            return "No relevant context found."
        
        context_parts = []
        for idx, (content, metadata, score) in enumerate(sources, 1):
            source_name = metadata.get("source", "Unknown")
            context_parts.append(
                f"[Source {idx} - {source_name}]\n{content}\n"
            )
        
        return "\n".join(context_parts)
    
    async def generate_answer(
        self,
        question: str,
        context_sources: list[tuple[str, dict, float]],
        conversation_history: Optional[list[dict]] = None
    ) -> tuple[str, dict]:
        """
        Generate an answer using the RAG approach
        """
        # Step 1: Format the context
        context = self._format_context(context_sources)
        
        # Step 2: Build the prompt
        full_question = f"""Context:
        {context}

        Question: {question}

        Based on the context above, please answer the question.
        If the context doesn't contain the answer, say so clearly."""
        
        # Step 3: Create messages for the chat
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=full_question)
        ]
        
        # Step 4: Generate response
        logger.info(f"Generating answer for: {question[:100]}")
        response = await self.llm.agenerate([messages])
        
        # Extract the answer
        answer = response.generations[0][0].text
        
        # Extract metadata
        metadata = {
            "model": settings.openai_model,
            "tokens_used": response.llm_output.get("token_usage", {}).get("total_tokens"),
            "sources_used": len(context_sources),
        }
        
        logger.info(f"Generated answer with {metadata['tokens_used']} tokens")
        return answer, metadata


# Singleton pattern
_llm_client = None

def get_llm_client() -> LLMClient:
    """Get or create LLM client"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client