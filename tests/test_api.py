"""Tests for API endpoints."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.chat_service import ChatService


class TestChatAPI:
    """Test suite for chat API endpoints."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "environment" in data
    
    @patch('app.api.routes_chat.ChatService')
    def test_chat_endpoint_success(self, mock_chat_service, client):
        """Test successful chat request."""
        # Setup mock service
        mock_response = Mock()
        mock_response.session_id = "test-session"
        mock_response.turn_id = "turn-123"
        mock_response.answer = Mock(plain_text="Hello!", markdown="**Hello!**")
        mock_response.sources = []
        mock_response.latency_ms = 500
        mock_response.trace_id = "trace-123"
        
        mock_service_instance = Mock()
        mock_service_instance.process_chat.return_value = mock_response
        mock_chat_service.return_value = mock_service_instance
        
        # Make request
        request_data = {
            "sessionId": "test-session",
            "message": "Hello, how are you?",
            "metadata": {"userId": "user-123", "lang": "en"}
        }
        
        response = client.post("/api/v1/chat", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["sessionId"] == "test-session"
        assert data["turnId"] == "turn-123"
        assert data["answer"]["plainText"] == "Hello!"
        assert data["answer"]["markdown"] == "**Hello!**"
        assert data["latencyMs"] == 500
        assert data["traceId"] == "trace-123"
    
    def test_chat_endpoint_validation_error(self, client):
        """Test chat endpoint with validation errors."""
        # Empty session ID
        request_data = {
            "sessionId": "",
            "message": "Hello"
        }
        
        response = client.post("/api/v1/chat", json=request_data)
        assert response.status_code == 422
        
        # Empty message
        request_data = {
            "sessionId": "test-session",
            "message": ""
        }
        
        response = client.post("/api/v1/chat", json=request_data)
        assert response.status_code == 422
    
    @patch('app.api.routes_chat.ChatService')
    def test_chat_endpoint_service_error(self, mock_chat_service, client):
        """Test chat endpoint with service error."""
        from app.core.errors import ChatbotError
        
        # Setup mock service to raise error
        mock_service_instance = Mock()
        mock_service_instance.process_chat.side_effect = ChatbotError("Service error")
        mock_chat_service.return_value = mock_service_instance
        
        request_data = {
            "sessionId": "test-session",
            "message": "Hello"
        }
        
        response = client.post("/api/v1/chat", json=request_data)
        
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "CHATBOT_ERROR"
    
    @patch('app.api.routes_chat.ChatService')
    def test_get_history_success(self, mock_chat_service, client):
        """Test successful history retrieval."""
        # Setup mock service
        mock_messages = [
            {
                "id": "msg-1",
                "session_id": "test-session",
                "role": "user",
                "content": "Hello",
                "created_at": "2023-01-01T00:00:00+00:00",
                "metadata": None
            },
            {
                "id": "msg-2",
                "session_id": "test-session", 
                "role": "assistant",
                "content": "Hi there!",
                "created_at": "2023-01-01T00:01:00+00:00",
                "metadata": None
            }
        ]
        
        mock_service_instance = Mock()
        mock_service_instance.get_session_history.return_value = mock_messages
        mock_chat_service.return_value = mock_service_instance
        
        response = client.get("/api/v1/sessions/test-session/history")
        
        assert response.status_code == 200
        data = response.json()
        assert data["sessionId"] == "test-session"
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"
        assert data["totalCount"] == 2
        assert data["hasMore"] is False
    
    def test_get_history_validation_error(self, client):
        """Test history endpoint with validation errors."""
        response = client.get("/api/v1/sessions//history")
        assert response.status_code == 404  # FastAPI routing error
    
    @patch('app.api.routes_chat.ChatService')
    def test_health_check_success(self, mock_chat_service, client):
        """Test successful health check."""
        # Setup mock service
        mock_service_instance = Mock()
        mock_service_instance.health_check.return_value = {
            "healthy": True,
            "dependencies": {
                "cosmos_db": True,
                "rag_service": True,
                "data_agent": True
            }
        }
        mock_chat_service.return_value = mock_service_instance
        
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "environment" in data
    
    @patch('app.api.routes_chat.ChatService')
    def test_healthz_healthy(self, mock_chat_service, client):
        """Test healthz endpoint when healthy."""
        mock_service_instance = Mock()
        mock_service_instance.health_check.return_value = {
            "healthy": True,
            "dependencies": {}
        }
        mock_chat_service.return_value = mock_service_instance
        
        response = client.get("/api/v1/healthz")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    @patch('app.api.routes_chat.ChatService')
    def test_healthz_unhealthy(self, mock_chat_service, client):
        """Test healthz endpoint when unhealthy."""
        mock_service_instance = Mock()
        mock_service_instance.health_check.return_value = {
            "healthy": False,
            "dependencies": {
                "cosmos_db": False
            }
        }
        mock_chat_service.return_value = mock_service_instance
        
        response = client.get("/api/v1/healthz")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"