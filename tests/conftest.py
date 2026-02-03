"""Test configuration and fixtures."""

import os
import sys
from unittest.mock import Mock

# Load .env file first (for integration tests with real credentials)
from dotenv import load_dotenv

# Load .env from project root (parent of tests/ directory)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path, override=False)  # Don't override existing env vars
    print(f"Loaded .env from {env_path}")
else:
    print(f"Warning: No .env file found at {env_path}, using test defaults")

# Set test environment variables ONLY if not already set (preserves .env for integration tests)
# This allows integration tests to use real credentials while unit tests use test values
test_env_vars = {
    "CLIENT_ID": os.getenv("CLIENT_ID") or "test-client-id",
    "TENANT_ID": os.getenv("TENANT_ID") or "test-tenant-id",
    "CLIENT_SECRET": os.getenv("CLIENT_SECRET") or "test-client-secret",
    "DATA_AGENT_URL": os.getenv("DATA_AGENT_URL") or "https://test.fabric.microsoft.com/api",
    "COSMOS_ENDPOINT": os.getenv("COSMOS_ENDPOINT") or "https://test.documents.azure.com:443/",
    "COSMOS_KEY": os.getenv("COSMOS_KEY") or "test-cosmos-key",
    "COSMOS_DATABASE": os.getenv("COSMOS_DATABASE") or "test-chatdb",
    "COSMOS_CONTAINER": os.getenv("COSMOS_CONTAINER") or "test-messages",
    "APP_ENV": "test",
    "LOG_LEVEL": "DEBUG",
    "RAG_PROVIDER": "none",
    "CORS_ORIGINS": "http://localhost:3000",
    "MAX_MESSAGE_LENGTH": "4000",
    "MAX_HISTORY_TURNS": "20",
    "REQUEST_TIMEOUT_SECS": "60",
}

os.environ.update(test_env_vars)

# Now safe to import app modules
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.cosmos_repo import CosmosDBRepository
from app.services.rag_service import RAGService
from app.services.data_agent_client import FabricDataAgentClient


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_cosmos_repo():
    """Mock Cosmos DB repository."""
    mock = Mock(spec=CosmosDBRepository)
    mock.get_last_n_messages.return_value = []
    mock.create_message.return_value = None
    return mock


@pytest.fixture
def mock_rag_service():
    """Mock RAG service."""
    mock = Mock(spec=RAGService)
    mock.is_available.return_value = False
    mock.retrieve.return_value = []
    return mock


@pytest.fixture
def mock_data_agent_client():
    """Mock Fabric Data Agent client."""
    mock = Mock(spec=FabricDataAgentClient)
    mock.invoke_agent.return_value = Mock(response="Test response")
    mock.health_check.return_value = True
    return mock


@pytest.fixture
def sample_chat_request():
    """Sample chat request for testing."""
    from app.models.dto import ChatRequest
    return ChatRequest(
        session_id="test-session-123",
        message="Hello, how can you help me?",
        metadata={"userId": "test-user", "lang": "en"}
    )