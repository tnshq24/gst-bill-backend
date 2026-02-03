"""Tests for Fabric Data Agent client."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import httpx

from app.services.data_agent_client import FabricDataAgentClient
from app.models.schemas import DataAgentRequest, DataAgentResponse
from app.core.errors import DataAgentError


class TestFabricDataAgentClient:
    """Test suite for Fabric Data Agent client."""
    
    @patch('app.services.data_agent_client.ClientSecretCredential')
    def test_initialization_success(self, mock_credential):
        """Test successful client initialization."""
        mock_credential.return_value = Mock()
        
        client = FabricDataAgentClient()
        
        assert client.credential is not None
        mock_credential.assert_called_once()
    
    @patch('app.services.data_agent_client.ClientSecretCredential')
    def test_initialization_failure(self, mock_credential):
        """Test initialization failure."""
        mock_credential.side_effect = Exception("Credential error")
        
        with pytest.raises(DataAgentError):
            FabricDataAgentClient()
    
    @patch('app.services.data_agent_client.ClientSecretCredential')
    def test_get_access_token_cached(self, mock_credential):
        """Test getting cached access token."""
        mock_token = Mock()
        mock_token.token = "test-token"
        mock_token.expires_on = 9999999999  # Far future
        
        mock_credential.return_value.get_token.return_value = mock_token
        
        client = FabricDataAgentClient()
        
        # First call should get token
        token1 = client._get_access_token()
        
        # Second call should use cached token
        token2 = client._get_access_token()
        
        assert token1 == "test-token"
        assert token2 == "test-token"
        mock_credential.return_value.get_token.assert_called_once()
    
    @patch('app.services.data_agent_client.ClientSecretCredential')
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_invoke_agent_success(self, mock_http_client, mock_credential):
        """Test successful agent invocation."""
        # Setup mocks
        mock_token = Mock()
        mock_token.token = "test-token"
        mock_token.expires_on = 9999999999
        mock_credential.return_value.get_token.return_value = mock_token
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Test response"}
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_http_client.return_value.__aenter__.return_value = mock_client_instance
        
        client = FabricDataAgentClient()
        
        request = DataAgentRequest(
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            context=None,
            system_instructions=None,
            max_tokens=None
        )
        
        response = await client.invoke_agent(request)
        
        assert response.response == "Test response"
        mock_client_instance.post.assert_called_once()
    
    @patch('app.services.data_agent_client.ClientSecretCredential')
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_invoke_agent_http_error(self, mock_http_client, mock_credential):
        """Test agent invocation with HTTP error."""
        # Setup mocks
        mock_token = Mock()
        mock_token.token = "test-token"
        mock_token.expires_on = 9999999999
        mock_credential.return_value.get_token.return_value = mock_token
        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"message": "Bad request"}}
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_http_client.return_value.__aenter__.return_value = mock_client_instance
        
        client = FabricDataAgentClient()
        
        request = DataAgentRequest(
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            context=None,
            system_instructions=None,
            max_tokens=None
        )
        
        with pytest.raises(DataAgentError) as exc_info:
            await client.invoke_agent(request)
        
        assert "Bad request" in str(exc_info.value)
        assert exc_info.value.status_code == 400
    
    @patch('app.services.data_agent_client.ClientSecretCredential')
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_invoke_agent_retry(self, mock_http_client, mock_credential):
        """Test agent invocation with retry logic."""
        # Setup mocks
        mock_token = Mock()
        mock_token.token = "test-token"
        mock_token.expires_on = 9999999999
        mock_credential.return_value.get_token.return_value = mock_token
        
        # First call fails with 500, second succeeds
        mock_error_response = Mock()
        mock_error_response.status_code = 500
        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"response": "Success"}
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = [mock_error_response, mock_success_response]
        mock_http_client.return_value.__aenter__.return_value = mock_client_instance
        
        client = FabricDataAgentClient()
        
        request = DataAgentRequest(
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            context=None,
            system_instructions=None,
            max_tokens=None
        )
        
        response = await client.invoke_agent(request, max_retries=1)
        
        assert response.response == "Success"
        assert mock_client_instance.post.call_count == 2
    
    @patch('app.services.data_agent_client.ClientSecretCredential')
    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_credential):
        """Test successful health check."""
        mock_token = Mock()
        mock_token.token = "test-token"
        mock_token.expires_on = 9999999999
        mock_credential.return_value.get_token.return_value = mock_token
        
        client = FabricDataAgentClient()
        is_healthy = await client.health_check()
        
        assert is_healthy is True