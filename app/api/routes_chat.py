"""API routes for chat endpoints."""

from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.core.config import settings
from app.core.errors import ChatbotError, ValidationError
from app.models.dto import (
    ChatRequest, 
    ChatResponse, 
    HistoryResponse, 
    ChatMessage,
    HealthResponse
)
from app.services.chat_service import ChatService

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["chat"])


def get_chat_service() -> ChatService:
    """Dependency to get chat service instance."""
    return ChatService()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    chat_service: ChatService = Depends(get_chat_service)
) -> ChatResponse:
    """
    Process a chat message and return the assistant's response.
    
    - **sessionId**: Unique identifier for the chat session
    - **message**: User message to process
    - **metadata**: Optional metadata (userId, lang, etc.)
    
    Returns the assistant's response in both plain text and markdown formats,
    along with sources if RAG is enabled.
    """
    # Get trace ID from request context
    trace_id = getattr(http_request.state, "trace_id", "unknown")
    
    # Validate request
    if not request.session_id.strip():
        raise ValidationError("Session ID cannot be empty")
    
    if not request.message.strip():
        raise ValidationError("Message cannot be empty")
    
    if len(request.message) > 4000:  # Will be overridden by settings, but as a safeguard
        raise ValidationError("Message is too long")
    
    try:
        # Process chat request
        response = await chat_service.process_chat(request, trace_id)
        return response
        
    except ChatbotError as e:
        logger.error(
            f"Chat processing error: {str(e)}",
            extra={
                "session_id": request.session_id,
                "error_code": e.error_code,
                "trace_id": trace_id
            }
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": e.error_code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in chat endpoint: {str(e)}",
            extra={
                "session_id": request.session_id,
                "trace_id": trace_id
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again later."
        )


@router.get("/sessions/{session_id}/history", response_model=HistoryResponse)
async def get_session_history(
    session_id: str,
    http_request: Request,
    limit: int = Query(default=20, ge=1, le=100, description="Number of messages to return"),
    offset: int = Query(default=0, ge=0, description="Number of messages to skip"),
    chat_service: ChatService = Depends(get_chat_service)
) -> HistoryResponse:
    """
    Get the conversation history for a specific session.
    
    - **session_id**: The session identifier
    - **limit**: Maximum number of messages to return (1-100)
    - **offset**: Number of messages to skip for pagination
    
    Returns paginated list of messages in chronological order.
    """
    trace_id = getattr(http_request.state, "trace_id", "unknown")
    
    if not session_id.strip():
        raise ValidationError("Session ID cannot be empty")
    
    try:
        # Get messages from chat service
        messages_data = await chat_service.get_session_history(
            session_id=session_id,
            limit=limit,
            offset=offset
        )
        
        # Convert to ChatMessage objects
        messages = [
            ChatMessage(
                id=msg["id"],
                session_id=msg["session_id"],
                role=msg["role"],
                content=msg["content"],
                created_at=datetime.fromisoformat(msg["created_at"].replace('Z', '+00:00')),
                metadata=msg.get("metadata")
            )
            for msg in messages_data
        ]
        
        # For simplicity, we'll assume there might be more messages
        # In a real implementation, you'd get the total count from the database
        has_more = len(messages) == limit
        
        return HistoryResponse(
            session_id=session_id,
            messages=messages,
            total_count=len(messages),  # This would be the actual total count from DB
            has_more=has_more
        )
        
    except ChatbotError as e:
        logger.error(
            f"History retrieval error: {str(e)}",
            extra={
                "session_id": session_id,
                "error_code": e.error_code,
                "trace_id": trace_id
            }
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": e.error_code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in history endpoint: {str(e)}",
            extra={
                "session_id": session_id,
                "trace_id": trace_id
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again later."
        )


@router.get("/health", response_model=HealthResponse)
async def health_check(
    chat_service: ChatService = Depends(get_chat_service)
) -> HealthResponse:
    """
    Health check endpoint for monitoring service status.
    
    Returns overall service health and dependency status.
    """
    try:
        # Get health status from chat service
        health_data = await chat_service.health_check()
        
        return HealthResponse(
            status="healthy" if health_data["healthy"] else "unhealthy",
            timestamp=datetime.utcnow(),
            environment=settings.app_env
        )
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}", exc_info=True)
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            environment=settings.app_env
        )


@router.get("/healthz")
async def healthz(
    chat_service: ChatService = Depends(get_chat_service)
) -> JSONResponse:
    """
    Simple health endpoint for load balancers.
    
    Returns HTTP 200 if service is healthy, 503 otherwise.
    """
    try:
        health_data = await chat_service.health_check()
        
        if health_data["healthy"]:
            return JSONResponse(
                content={"status": "ok"},
                status_code=200
            )
        else:
            return JSONResponse(
                content={"status": "error", "dependencies": health_data["dependencies"]},
                status_code=503
            )
            
    except Exception as e:
        logger.error(f"Healthz endpoint error: {str(e)}", exc_info=True)
        return JSONResponse(
            content={"status": "error"},
            status_code=503
        )