"""RAG service for document retrieval and context augmentation."""

from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
import re

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import Document
from app.core.errors import RAGError

logger = get_logger(__name__)


class RAGService(ABC):
    """Abstract base class for RAG implementations."""
    
    @abstractmethod
    async def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Document]:
        """Retrieve relevant documents for a query."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the RAG service is available."""
        pass


class AzureAISearchService(RAGService):
    """RAG implementation using Azure AI Search."""
    
    def __init__(self):
        """Initialize Azure AI Search client."""
        self.search_client = None
        self.is_initialized = False
        self._initialize()
    
    def _initialize(self):
        """Initialize Azure AI Search client."""
        try:
            if settings.rag_provider != "azure_ai_search":
                logger.info("RAG provider is not Azure AI Search, skipping initialization")
                return
            
            if not settings.azure_search_endpoint or not settings.azure_search_key:
                logger.warning("Azure AI Search credentials not configured")
                return
            
            from azure.search.documents import SearchClient
            from azure.core.credentials import AzureKeyCredential
            
            credential = AzureKeyCredential(settings.azure_search_key)
            self.search_client = SearchClient(
                endpoint=settings.azure_search_endpoint,
                index_name=settings.azure_search_index,
                credential=credential
            )
            
            self.is_initialized = True
            logger.info("Azure AI Search client initialized successfully")
            
        except ImportError:
            logger.error("Azure AI Search SDK not installed. Install with: pip install azure-search-documents")
            raise RAGError("Azure AI Search SDK not available")
        except Exception as e:
            logger.error(f"Failed to initialize Azure AI Search: {str(e)}", exc_info=True)
            raise RAGError(f"Failed to initialize Azure AI Search: {str(e)}")
    
    async def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Document]:
        """Retrieve documents from Azure AI Search."""
        if not self.is_available():
            logger.warning("Azure AI Search is not available, returning empty results")
            return []
        
        top_k = top_k or settings.rag_top_k
        
        try:
            # Sanitize query
            sanitized_query = self._sanitize_query(query)
            
            # Execute search
            if self.search_client is None:
                logger.error("Search client not initialized")
                return []
            results = self.search_client.search(
                search_text=sanitized_query,
                top=top_k,
                include_total_count=True,
                query_type="semantic" if self._supports_semantic_search() else "full"
            )
            
            # Convert to Document objects
            documents = []
            for result in results:
                doc = Document(
                    id=result.get("id", ""),
                    title=result.get("title", ""),
                    content=result.get("content", ""),
                    url=result.get("url"),
                    score=result.get("@search.score"),
                    metadata=result.get("metadata", {})
                )
                documents.append(doc)
            
            logger.info(
                f"Retrieved {len(documents)} documents from Azure AI Search",
                extra={
                    "query_length": len(query),
                    "top_k": top_k,
                    "results_count": len(documents)
                }
            )
            
            return documents
            
        except Exception as e:
            logger.error(f"Azure AI Search query failed: {str(e)}", exc_info=True)
            raise RAGError(f"Search query failed: {str(e)}")
    
    def _sanitize_query(self, query: str) -> str:
        """Sanitize and prepare query for search."""
        # Remove special characters that might break search
        sanitized = re.sub(r'[^\w\s\-.,!?;:]', ' ', query)
        # Normalize whitespace
        sanitized = ' '.join(sanitized.split())
        return sanitized.strip()
    
    def _supports_semantic_search(self) -> bool:
        """Check if semantic search is supported (placeholder logic)."""
        # In a real implementation, you would check if the index has semantic configuration
        return True
    
    def is_available(self) -> bool:
        """Check if Azure AI Search is available."""
        return self.is_initialized and self.search_client is not None
    
    async def health_check(self) -> bool:
        """Check if Azure AI Search is healthy."""
        if not self.is_available():
            return False
        
        try:
            # Simple health check - try to get service statistics
            if self.search_client is None:
                return False
            self.search_client.get_document_count()
            return True
        except Exception as e:
            logger.error(f"Azure AI Search health check failed: {str(e)}")
            return False


class InMemoryRAGService(RAGService):
    """In-memory RAG service for development and testing."""
    
    def __init__(self):
        """Initialize with some sample documents."""
        self.documents = [
            Document(
                id="doc1",
                title="Sample Document 1",
                content="This is a sample document about enterprise policies and procedures.",
                url="https://example.com/doc1",
                score=0.9
            ),
            Document(
                id="doc2", 
                title="Sample Document 2",
                content="This document contains information about HR guidelines and employee benefits.",
                url="https://example.com/doc2",
                score=0.8
            ),
            Document(
                id="doc3",
                title="Sample Document 3", 
                content="Technical documentation for software development processes and coding standards.",
                url="https://example.com/doc3",
                score=0.7
            )
        ]
        logger.info("In-memory RAG service initialized with sample documents")
    
    async def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Document]:
        """Retrieve documents using simple keyword matching."""
        top_k = top_k or settings.rag_top_k
        query_lower = query.lower()
        
        # Simple scoring based on keyword overlap
        scored_docs = []
        for doc in self.documents:
            score = 0.0
            query_words = query_lower.split()
            content_words = doc.content.lower().split()
            title_words = doc.title.lower().split()
            
            # Count matching words
            for word in query_words:
                if word in content_words:
                    score += 0.1
                if word in title_words:
                    score += 0.2
            
            if score > 0:
                doc_copy = Document(**doc.model_dump())
                doc_copy.score = score
                scored_docs.append(doc_copy)
        
        # Sort by score and return top_k
        scored_docs.sort(key=lambda x: x.score or 0, reverse=True)
        
        logger.debug(
            f"In-memory RAG retrieved {len(scored_docs[:top_k])} documents",
            extra={
                "query": query,
                "results_count": len(scored_docs[:top_k])
            }
        )
        
        return scored_docs[:top_k]
    
    def is_available(self) -> bool:
        """In-memory service is always available."""
        return True


class NoOpRAGService(RAGService):
    """No-op RAG service that returns empty results."""
    
    async def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Document]:
        """Return empty results."""
        logger.debug("NoOp RAG service returning empty results")
        return []
    
    def is_available(self) -> bool:
        """No-op service is always available."""
        return True


class RAGServiceFactory:
    """Factory for creating RAG service instances."""
    
    @staticmethod
    def create_service() -> RAGService:
        """Create appropriate RAG service based on configuration."""
        provider = settings.rag_provider.lower()
        
        if provider == "azure_ai_search":
            try:
                return AzureAISearchService()
            except RAGError as e:
                logger.warning(f"Failed to create Azure AI Search service: {e}. Falling back to NoOp service.")
                return NoOpRAGService()
        elif provider == "none":
            return NoOpRAGService()
        else:
            logger.warning(f"Unknown RAG provider: {provider}. Using NoOp service.")
            return NoOpRAGService()


def format_context(documents: List[Document], max_tokens: int = 2000) -> str:
    """Format retrieved documents into context string for the agent."""
    if not documents:
        return ""
    
    context_parts = ["--- Retrieved Context ---"]
    
    for i, doc in enumerate(documents, 1):
        # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
        doc_text = f"Document {i}: {doc.title}\n{doc.content[:1000]}"
        
        # Check if we're approaching the token limit
        current_context = "\n\n".join(context_parts + [doc_text])
        if len(current_context) * 0.25 > max_tokens:  # Rough token estimation
            context_parts.append(f"... ({len(documents) - i + 1} more documents)")
            break
        
        context_parts.append(doc_text)
    
    context_parts.append("--- End of Context ---")
    return "\n\n".join(context_parts)