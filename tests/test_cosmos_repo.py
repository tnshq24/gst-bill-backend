"""Tests for Cosmos DB repository."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from app.services.cosmos_repo import CosmosDBRepository
from app.models.schemas import CosmosMessage
from app.core.errors import CosmosDBError


class TestCosmosDBRepository:
    """Test suite for Cosmos DB repository."""
    
    @patch('app.services.cosmos_repo.CosmosClient')
    def test_initialization_success(self, mock_cosmos_client):
        """Test successful initialization."""
        # Mock client setup
        mock_db = Mock()
        mock_container = Mock()
        mock_cosmos_client.return_value.get_database_client.return_value = mock_db
        mock_db.get_container_client.return_value = mock_container
        
        repo = CosmosDBRepository()
        
        assert repo.client is not None
        assert repo.messages_container is not None
    
    @patch('app.services.cosmos_repo.CosmosClient')
    def test_initialization_failure(self, mock_cosmos_client):
        """Test initialization failure."""
        mock_cosmos_client.side_effect = Exception("Connection failed")
        
        with pytest.raises(CosmosDBError):
            CosmosDBRepository()
    
    @patch('app.services.cosmos_repo.CosmosClient')
    @pytest.mark.asyncio
    async def test_create_message_success(self, mock_cosmos_client):
        """Test successful message creation."""
        # Setup mocks
        mock_container = Mock()
        mock_cosmos_client.return_value.get_database_client.return_value.get_container_client.return_value = mock_container
        
        repo = CosmosDBRepository()
        message = CosmosMessage(
            session_id="test-session",
            role="user",
            content="Hello world",
            turn_id="turn-123"
        )
        
        await repo.create_message(message)
        
        mock_container.create_item.assert_called_once()
    
    @patch('app.services.cosmos_repo.CosmosClient')
    @pytest.mark.asyncio
    async def test_get_session_messages_success(self, mock_cosmos_client):
        """Test successful message retrieval."""
        # Setup mocks
        mock_container = Mock()
        mock_container.query_items.return_value = [
            {
                "id": "msg-1",
                "sessionId": "test-session",
                "role": "user",
                "content": "Hello",
                "createdAt": "2023-01-01T00:00:00Z",
                "metadata": None,
                "turnId": "turn-1"
            },
            {
                "id": "msg-2", 
                "sessionId": "test-session",
                "role": "assistant",
                "content": "Hi there!",
                "createdAt": "2023-01-01T00:01:00Z",
                "metadata": None,
                "turnId": "turn-1"
            }
        ]
        mock_cosmos_client.return_value.get_database_client.return_value.get_container_client.return_value = mock_container
        
        repo = CosmosDBRepository()
        messages = await repo.get_session_messages("test-session")
        
        assert len(messages) == 2
        assert messages[0].role == "user"  # Should be in chronological order
        assert messages[1].role == "assistant"
    
    @patch('app.services.cosmos_repo.CosmosClient')
    def test_health_check_success(self, mock_cosmos_client):
        """Test successful health check."""
        mock_db = Mock()
        mock_cosmos_client.return_value.get_database_client.return_value = mock_db
        
        repo = CosmosDBRepository()
        is_healthy = repo.health_check()
        
        assert is_healthy is True
        mock_db.read.assert_called_once()
    
    @patch('app.services.cosmos_repo.CosmosClient')
    def test_health_check_failure(self, mock_cosmos_client):
        """Test health check failure."""
        mock_cosmos_client.return_value.get_database_client.return_value.read.side_effect = Exception("DB error")
        
        repo = CosmosDBRepository()
        is_healthy = repo.health_check()
        
        assert is_healthy is False