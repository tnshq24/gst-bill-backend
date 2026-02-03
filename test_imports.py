"""Test imports one by one."""
print("Testing imports...")

try:
    from fastapi import FastAPI
    print("✓ FastAPI")
    
    from fastapi.middleware.cors import CORSMiddleware
    print("✓ CORSMiddleware")
    
    from app.core.config import settings
    print("✓ settings")
    print(f"  cors_origins_list type: {type(settings.cors_origins_list)}")
    print(f"  cors_origins_list value: {settings.cors_origins_list}")
    
    from app.core.logging import setup_logging, LoggingMiddleware, get_logger
    print("✓ logging")
    
    from app.core.errors import (
        ChatbotError, 
        chatbot_exception_handler,
        http_exception_handler,
        validation_exception_handler,
        general_exception_handler
    )
    print("✓ errors")
    
    from app.api.routes_chat import router as chat_router
    print("✓ routes")
    
    print("\nAll imports successful!")
    
    # Try creating app
    print("\nCreating app...")
    app = FastAPI()
    print("✓ FastAPI app created")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    print("✓ CORS middleware added")
    
    app.add_middleware(LoggingMiddleware)
    print("✓ Logging middleware added")
    
    app.add_exception_handler(ChatbotError, chatbot_exception_handler)
    print("✓ ChatbotError handler added")
    
    print("\n✅ App created successfully!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()