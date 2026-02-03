#!/usr/bin/env python3
"""Quick test to verify configuration loads correctly."""

import os
import sys

# Set test environment variables
os.environ.update({
    "CLIENT_ID": "test-client-id",
    "TENANT_ID": "test-tenant-id",
    "CLIENT_SECRET": "test-secret",
    "DATA_AGENT_URL": "https://test.com/api",
    "COSMOS_ENDPOINT": "https://test.documents.azure.com",
    "COSMOS_KEY": "test-key",
    "CORS_ORIGINS": "http://localhost:3000,http://localhost:8080"
})

try:
    from app.core.config import get_settings
    
    settings = get_settings()
    
    print("Configuration loaded successfully!")
    print("\nSettings:")
    print(f"  - App Environment: {settings.app_env}")
    print(f"  - CORS Origins: {settings.cors_origins_list}")
    print(f"  - RAG Provider: {settings.rag_provider}")
    print(f"  - Max History: {settings.max_history_turns}")
    
except Exception as e:
    print(f"Error loading configuration: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)