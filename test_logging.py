#!/usr/bin/env python3
"""Quick test to verify logging works correctly."""

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
    "CORS_ORIGINS": "http://localhost:3000"
})

try:
    # Import and setup logging
    from app.core.logging import setup_logging, get_logger
    setup_logging("INFO")
    
    # Test logger
    logger = get_logger("test")
    logger.info("Test log message")
    logger.warning("Test warning message")
    logger.error("Test error message")
    
    print("Logging test passed!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)