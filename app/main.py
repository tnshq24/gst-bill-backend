"""FastAPI application factory and configuration."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.logging import setup_logging, LoggingMiddleware, get_logger
from app.core.errors import (
    ChatbotError, 
    chatbot_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from app.api.routes_chat import router as chat_router

# Setup logging
setup_logging(settings.log_level)

# Create FastAPI app
app = FastAPI(
    title="Chatbot Avatar Backend",
    description="Backend API for chatbot avatar application with RAG and Fabric Data Agent integration",
    version="1.0.0",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
)

# Add CORS middleware FIRST
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add logging middleware SECOND
app.add_middleware(LoggingMiddleware)

# Add exception handlers
app.add_exception_handler(ChatbotError, chatbot_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(chat_router)

# Define startup event
@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger = get_logger(__name__)
    logger.info(
        "Chatbot Avatar Backend starting up",
        extra={
            "environment": settings.app_env,
            "port": settings.app_port,
            "rag_provider": settings.rag_provider
        }
    )

# Define shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger = get_logger(__name__)
    logger.info("Chatbot Avatar Backend shutting down")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Chatbot Avatar Backend API",
        "version": "1.0.0",
        "environment": settings.app_env,
        "docs_url": "/docs" if settings.is_dev else None
    }


def create_app():
    """Factory function for creating app (for gunicorn compatibility)."""
    return app