"""Structured logging configuration for the application."""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variables for trace propagation
trace_id_var: ContextVar[str] = ContextVar("trace_id")
session_id_var: ContextVar[str] = ContextVar("session_id")


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
# Add trace context if available
        trace_id = trace_id_var.get(None)
        if trace_id:
            log_data["trace_id"] = trace_id
        
        session_id = session_id_var.get(None)
        if session_id:
            log_data["session_id"] = session_id
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname", 
                "filename", "module", "lineno", "funcName", "created", 
                "msecs", "relativeCreated", "thread", "threadName", 
                "processName", "process", "getMessage", "exc_text", 
                "exc_info", "stack_info", "traceback"
            } and not key.startswith("_"):
                log_data[key] = value
        
        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove default handlers
    logger.handlers.clear()
    
    # Console handler with JSON formatting
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # Configure specific loggers
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging and trace ID injection."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and add logging context."""
        # Generate trace ID for the request
        trace_id = str(uuid.uuid4())
        trace_id_var.set(trace_id)
        
        # Extract session ID from path if available
        session_id = None
        if "/sessions/" in request.url.path:
            path_parts = request.url.path.split("/")
            try:
                session_idx = path_parts.index("sessions")
                if session_idx + 1 < len(path_parts):
                    session_id = path_parts[session_idx + 1]
                    session_id_var.set(session_id)
            except (ValueError, IndexError):
                pass
        
        # Log request start
        logger = logging.getLogger("app.request")
        start_time = time.time()
        
        logger.info(
            "Request started",
            extra={
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "client_host": request.client.host if request.client else None,
                "trace_id": trace_id,
                "session_id": session_id,
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = round((time.time() - start_time) * 1000)
            
            # Log request completion
            logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "trace_id": trace_id,
                    "session_id": session_id,
                }
            )
            
            # Add trace ID to response headers
            response.headers["X-Trace-ID"] = trace_id
            
            return response
            
        except Exception as e:
            # Log request error
            duration_ms = round((time.time() - start_time) * 1000)
            
            logger.error(
                "Request failed",
                extra={
                    "method": request.method,
                    "url": str(request.url),
                    "error": str(e),
                    "duration_ms": duration_ms,
                    "trace_id": trace_id,
                    "session_id": session_id,
                },
                exc_info=True
            )
            raise


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(name)