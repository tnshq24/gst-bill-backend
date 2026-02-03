"""Custom exceptions and error handlers for the application."""

from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class ChatbotError(Exception):
    """Base exception for chatbot application."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code or "CHATBOT_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(ChatbotError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIG_ERROR", details)


class CosmosDBError(ChatbotError):
    """Raised when Cosmos DB operations fail."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "COSMOS_ERROR", details)


class DataAgentError(ChatbotError):
    """Raised when Fabric Data Agent operations fail."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        self.status_code = status_code
        super().__init__(message, "DATA_AGENT_ERROR", details)


class RAGError(ChatbotError):
    """Raised when RAG operations fail."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "RAG_ERROR", details)


class ValidationError(ChatbotError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", details)


async def chatbot_exception_handler(request: Request, exc: ChatbotError) -> JSONResponse:
    """Handle custom chatbot exceptions."""
    trace_id = getattr(request.state, "trace_id", None)
    
    error_response = {
        "error": {
            "code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
        "trace_id": trace_id,
    }
    
    # Determine appropriate status code based on error type
    status_code = 500
    if isinstance(exc, ValidationError):
        status_code = 400
    elif isinstance(exc, DataAgentError) and exc.status_code:
        status_code = exc.status_code
    elif isinstance(exc, ConfigurationError):
        status_code = 503
    
    logger.error(
        f"Chatbot error: {exc.error_code}",
        extra={
            "error_code": exc.error_code,
            "error_message": exc.message,
            "error_details": exc.details,
            "trace_id": trace_id,
        },
        exc_info=type(exc) not in [ValidationError, DataAgentError]
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""
    trace_id = getattr(request.state, "trace_id", None)
    
    error_response = {
        "error": {
            "code": f"HTTP_{exc.status_code}",
            "message": exc.detail,
        },
        "trace_id": trace_id,
    }
    
    logger.warning(
        f"HTTP error: {exc.status_code}",
        extra={
            "status_code": exc.status_code,
            "error_message": exc.detail,
            "trace_id": trace_id,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors."""
    trace_id = getattr(request.state, "trace_id", None)
    
    # Format validation errors for better readability
    formatted_errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        formatted_errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"],
        })
    
    error_response = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"validation_errors": formatted_errors},
        },
        "trace_id": trace_id,
    }
    
    logger.warning(
        "Validation error",
        extra={
            "validation_errors": formatted_errors,
            "trace_id": trace_id,
        }
    )
    
    return JSONResponse(
        status_code=422,
        content=error_response,
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions."""
    trace_id = getattr(request.state, "trace_id", None)
    
    error_response = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Please try again later.",
        },
        "trace_id": trace_id,
    }
    
    logger.error(
        "Unhandled exception",
        extra={
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "trace_id": trace_id,
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response,
    )