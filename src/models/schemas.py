"""
Request and Response Models
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


# ============= REQUEST MODELS =============

class ChatRequest(BaseModel):
    """
    What the user sends to us
    """
    question: str = Field(
        ...,  # ... means required
        min_length=1,
        max_length=1000,
        description="User's question about Ashish"
    )
    conversation_id: Optional[UUID] = Field(
        default=None,
        description="To continue a conversation, pass the previous conversation_id"
    )
    stream: bool = Field(
        default=False,
        description="Set true for streaming response"
    )
    
    # Example of what this looks like:
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is Ashish's experience with Python?",
                "conversation_id": None,
                "stream": False
            }
        }


# ============= RESPONSE MODELS =============

class SourceDocument(BaseModel):
    """
    A piece of retrieved context from the knowledge base
    """
    content: str = Field(..., description="The text content")
    metadata: dict = Field(default_factory=dict, description="File name, etc.")
    relevance_score: Optional[float] = Field(
        default=None,
        description="How relevant this is (0-1, higher is better)"
    )


class ChatResponse(BaseModel):
    """
    What we send back to the user
    """
    message_id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID = Field(default_factory=uuid4)
    answer: str = Field(..., description="The AI-generated answer")
    sources: list[SourceDocument] = Field(
        default_factory=list,
        description="Sources used to generate the answer"
    )
    confidence: Optional[float] = Field(
        default=None,
        description="How confident we are in the answer (0-1)"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    model_used: str = Field(..., description="Which LLM model was used")
    tokens_used: Optional[int] = None


class ErrorResponse(BaseModel):
    """
    Standard error format
    """
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    environment: str
    checks: dict[str, bool] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)