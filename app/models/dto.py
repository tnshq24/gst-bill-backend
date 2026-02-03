"""Pydantic DTOs for API request/response models."""

from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator
import re


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    session_id: str = Field(..., alias="sessionId", description="Unique identifier for the chat session")
    message: str = Field(..., description="User message to process", min_length=1, max_length=4000)
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata", description="Optional metadata (userId, lang, etc.)")
    
    class Config:
        populate_by_name = True
    
    @validator('session_id')
    def validate_session_id(cls, v):
        if not v or not v.strip():
            raise ValueError("Session ID cannot be empty")
        return v.strip()
    
    @validator('message')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        # Remove extra whitespace but preserve sentence structure
        return ' '.join(v.split())


class AnswerResponse(BaseModel):
    """Response model for the assistant's answer."""
    plain_text: str = Field(..., description="Response with markdown formatting removed")
    markdown: str = Field(..., description="Response with markdown formatting preserved")


class Source(BaseModel):
    """Model for retrieved source information."""
    title: str = Field(..., description="Title of the source document")
    url: Optional[str] = Field(None, description="URL to the source document")
    snippet: str = Field(..., description="Relevant snippet from the source")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    session_id: str = Field(..., description="Session ID for the chat")
    turn_id: str = Field(..., description="Unique identifier for this conversation turn")
    answer: AnswerResponse = Field(..., description="Assistant's response")
    sources: Optional[List[Source]] = Field(default=None, description="Sources used for RAG (if applicable)")
    latency_ms: int = Field(..., description="Total processing time in milliseconds")
    trace_id: str = Field(..., description="Trace ID for debugging")


class ChatMessage(BaseModel):
    """Model for individual chat messages in history."""
    id: str = Field(..., description="Unique message identifier")
    session_id: str = Field(..., description="Session identifier")
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(..., description="Message creation timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ['user', 'assistant']:
            raise ValueError("Role must be 'user' or 'assistant'")
        return v


class HistoryResponse(BaseModel):
    """Response model for chat history endpoint."""
    session_id: str = Field(..., description="Session ID")
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    total_count: int = Field(..., description="Total number of messages")
    has_more: bool = Field(..., description="Whether more messages are available")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Current timestamp")
    version: str = Field(default="1.0.0", description="API version")
    environment: str = Field(..., description="Running environment")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: Dict[str, Any] = Field(..., description="Error details")
    trace_id: Optional[str] = Field(None, description="Trace ID for debugging")


def strip_markdown(text: str) -> str:
    """Remove markdown formatting from text while preserving readability."""
    if not text:
        return ""
    
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Remove bold/italic formatting
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    
    # Remove headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    
    # Remove links but keep the text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # Remove list markers
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove blockquotes
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    
    # Remove horizontal rules
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    # Clean up extra whitespace
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    text = text.strip()
    
    return text

def clean_plain_text(text: str) -> str:
    """Normalize plain text for TTS by removing non-letter characters."""
    if not text:
        return ""
    text = re.sub(r"[^A-Za-z ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
