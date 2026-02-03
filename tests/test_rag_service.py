"""Tests for RAG service."""

import pytest
from unittest.mock import Mock, patch

from app.services.rag_service import (
    RAGServiceFactory,
    AzureAISearchService,
    InMemoryRAGService,
    NoOpRAGService,
    format_context
)
from app.models.schemas import Document
from app.core.errors import RAGError


class TestRAGServiceFactory:
    """Test suite for RAG service factory."""
    
    @patch('app.services.rag_service.settings')
    def test_create_azure_search_service(self, mock_settings):
        """Test creating Azure AI Search service."""
        mock_settings.rag_provider = "azure_ai_search"
        
        with patch('app.services.rag_service.AzureAISearchService') as mock_service:
            mock_service.return_value = Mock()
            service = RAGServiceFactory.create_service()
            mock_service.assert_called_once()
    
    @patch('app.services.rag_service.settings')
    def test_create_noop_service(self, mock_settings):
        """Test creating NoOp service."""
        mock_settings.rag_provider = "none"
        
        service = RAGServiceFactory.create_service()
        assert isinstance(service, NoOpRAGService)
    
    @patch('app.services.rag_service.settings')
    def test_fallback_to_noop_on_error(self, mock_settings):
        """Test fallback to NoOp service on Azure Search error."""
        mock_settings.rag_provider = "azure_ai_search"
        
        with patch('app.services.rag_service.AzureAISearchService') as mock_service:
            mock_service.side_effect = RAGError("Initialization failed")
            service = RAGServiceFactory.create_service()
            assert isinstance(service, NoOpRAGService)


class TestInMemoryRAGService:
    """Test suite for in-memory RAG service."""
    
    @pytest.mark.asyncio
    async def test_retrieve_with_matches(self):
        """Test document retrieval with matches."""
        service = InMemoryRAGService()
        
        # Query that should match the enterprise policies document
        documents = await service.retrieve("enterprise policies")
        
        assert len(documents) > 0
        assert any("enterprise policies" in doc.content.lower() for doc in documents)
        assert all(doc.score is not None and doc.score > 0 for doc in documents)
    
    @pytest.mark.asyncio
    async def test_retrieve_no_matches(self):
        """Test document retrieval with no matches."""
        service = InMemoryRAGService()
        
        # Query that should not match any documents
        documents = await service.retrieve("xyz123 abc456")
        
        assert len(documents) == 0
    
    def test_is_available(self):
        """Test that in-memory service is always available."""
        service = InMemoryRAGService()
        assert service.is_available() is True


class TestNoOpRAGService:
    """Test suite for NoOp RAG service."""
    
    @pytest.mark.asyncio
    async def test_retrieve_always_empty(self):
        """Test that NoOp service always returns empty results."""
        service = NoOpRAGService()
        
        documents = await service.retrieve("any query")
        assert documents == []
    
    def test_is_available(self):
        """Test that NoOp service is always available."""
        service = NoOpRAGService()
        assert service.is_available() is True


class TestContextFormatting:
    """Test suite for context formatting."""
    
    def test_format_context_empty(self):
        """Test formatting empty document list."""
        result = format_context([])
        assert result == ""
    
    def test_format_context_single_document(self):
        """Test formatting single document."""
        documents = [
            Document(
                id="doc1",
                title="Test Doc",
                content="This is test content."
            )
        ]
        
        result = format_context(documents)
        
        assert "Document 1: Test Doc" in result
        assert "This is test content." in result
        assert "--- Retrieved Context ---" in result
        assert "--- End of Context ---" in result
    
    def test_format_context_multiple_documents(self):
        """Test formatting multiple documents."""
        documents = [
            Document(
                id="doc1",
                title="First Doc",
                content="First content."
            ),
            Document(
                id="doc2", 
                title="Second Doc",
                content="Second content."
            )
        ]
        
        result = format_context(documents)
        
        assert "Document 1: First Doc" in result
        assert "Document 2: Second Doc" in result
        assert "First content." in result
        assert "Second content." in result
    
    def test_format_context_token_limit(self):
        """Test token limit enforcement."""
        # Create a document with very long content
        long_content = "word " * 1000  # ~5000 tokens
        documents = [
            Document(
                id="doc1",
                title="Long Doc",
                content=long_content
            )
        ]
        
        result = format_context(documents, max_tokens=100)
        
        # Should truncate the content
        assert "Document 1: Long Doc" in result
        assert "more documents" not in result  # Only one document, so no truncation message
        # Content should be limited
        assert len(result) < len(long_content)