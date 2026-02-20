"""
Chat API Routes
Handles chat-related endpoints
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from src.models.schemas import ChatRequest, ChatResponse, ErrorResponse
from src.services.chat_service import get_chat_service, ChatService
from src.core.security.auth import verify_api_key, limiter, get_rate_limit_string

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/ask",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Ask a question about Ashish",
    description="Submit a question and get an AI-generated answer based on RAG retrieval"
)
@limiter.limit(get_rate_limit_string())
async def ask_question(
    request: Request,
    chatRequest: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
    _: str = Depends(verify_api_key)
) -> ChatResponse:
    """
    Ask a question about Ashish
    
    - **question**: The question to ask (required)
    - **conversation_id**: Optional UUID to maintain conversation context
    - **stream**: Whether to stream the response (not used in this endpoint)
    """
    try:
        logger.info(f"Received question: {chatRequest.question[:100]}")
        response = await chat_service.ask_question(chatRequest)
        return response
        
    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process question"
        )


@router.post(
    "/ask/stream",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question with streaming response",
    description="Submit a question and get a streamed AI-generated answer"
)
@limiter.limit(get_rate_limit_string())
async def ask_question_stream(
    request: Request,
    chatRequest: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
    _: str = Depends(verify_api_key)
) -> StreamingResponse:
    """
    Ask a question with streaming response
    
    The response will be streamed as Server-Sent Events (SSE)
    """
    try:
        logger.info(f"Received streaming question: {request.question[:100]}")
        
        async def generate():
            try:
                async for chunk in chat_service.ask_question_stream(request):
                    # Send as SSE format
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Error during streaming: {e}")
                yield f"data: Error: {str(e)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        logger.error(f"Error setting up stream: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stream response"
        )


@router.get(
    "/conversation/{conversation_id}/summary",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get conversation summary",
    description="Get a summary of a conversation by ID"
)
async def get_conversation_summary(
    conversation_id: UUID,
    chat_service: ChatService = Depends(get_chat_service),
    _: str = Depends(verify_api_key)
) -> dict:
    """Get a summary of the conversation"""
    try:
        summary = await chat_service.get_conversation_summary(conversation_id)
        
        if summary is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        return {"conversation_id": str(conversation_id), "summary": summary}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation summary"
        )


@router.delete(
    "/conversation/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear conversation history",
    description="Delete a conversation and its history"
)
async def clear_conversation(
    conversation_id: UUID,
    chat_service: ChatService = Depends(get_chat_service),
    _: str = Depends(verify_api_key)
) -> None:
    """Clear conversation history"""
    try:
        cleared = chat_service.clear_conversation(conversation_id)
        
        if not cleared:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        logger.info(f"Cleared conversation {conversation_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear conversation"
        )


@router.get(
    "/stats",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get chat statistics",
    description="Get statistics about active conversations"
)
async def get_chat_stats(
    chat_service: ChatService = Depends(get_chat_service),
    _: str = Depends(verify_api_key)
) -> dict:
    """Get chat statistics"""
    try:
        return {
            "active_conversations": chat_service.get_conversation_count()
        }
    except Exception as e:
        logger.error(f"Error getting chat stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat statistics"
        )