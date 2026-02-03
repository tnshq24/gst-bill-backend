"""Pydantic schemas for Cosmos DB data models."""

from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class CosmosMessage(BaseModel):
    """Schema for Cosmos DB message documents."""
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique message identifier")
    session_id: str = Field(..., description="Session identifier for partitioning")
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Message creation timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")
    turn_id: Optional[str] = Field(None, description="Optional turn identifier for grouping")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Cosmos DB storage."""
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "role": self.role,
            "content": self.content,
            "createdAt": self.created_at.isoformat(),
            "metadata": self.metadata,
            "turnId": self.turn_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CosmosMessage":
        """Create from Cosmos DB document."""
        return cls(
            id=data["id"],
            session_id=data["sessionId"],
            role=data["role"],
            content=data["content"],
            created_at=datetime.fromisoformat(data["createdAt"].replace('Z', '+00:00')),
            metadata=data.get("metadata"),
            turn_id=data.get("turnId")
        )


class CosmosSession(BaseModel):
    """Schema for Cosmos DB session metadata documents."""
    id: str = Field(..., description="Session ID (same as document ID)")
    user_id: Optional[str] = Field(None, description="User identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation timestamp")
    last_active_at: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    message_count: int = Field(default=0, description="Total messages in session")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional session metadata")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Cosmos DB storage."""
        return {
            "id": self.id,
            "userId": self.user_id,
            "createdAt": self.created_at.isoformat(),
            "lastActiveAt": self.last_active_at.isoformat(),
            "messageCount": self.message_count,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CosmosSession":
        """Create from Cosmos DB document."""
        return cls(
            id=data["id"],
            user_id=data.get("userId"),
            created_at=datetime.fromisoformat(data["createdAt"].replace('Z', '+00:00')),
            last_active_at=datetime.fromisoformat(data["lastActiveAt"].replace('Z', '+00:00')),
            message_count=data.get("messageCount", 0),
            metadata=data.get("metadata")
        )


class Document(BaseModel):
    """Model for retrieved documents from RAG."""
    id: str
    title: str
    content: str
    url: Optional[str] = None
    score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_source(self):
        """Convert to API response source format."""
        from app.models.dto import Source as DtoSource
        return DtoSource(
            title=self.title,
            url=self.url,
            snippet=self.content[:200] + "..." if len(self.content) > 200 else self.content
        )


class DataAgentRequest(BaseModel):
    """Request model for Fabric Data Agent."""
    messages: List[Dict[str, str]] = Field(..., description="Conversation history")
    context: Optional[str] = Field(None, description="Additional context from RAG")
    system_instructions: Optional[str] = Field(None, description="System instructions for the agent")
    temperature: float = Field(0.7, description="Temperature for response generation", ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, description="Maximum tokens in response")


class DataAgentResponse(BaseModel):
    """Response model from Fabric Data Agent."""
    response: str = Field(..., description="Agent's response")
    usage: Optional[Dict[str, Any]] = Field(None, description="Token usage information")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional response metadata")