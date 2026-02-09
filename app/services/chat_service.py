"""Chat service orchestrator for handling conversation flow."""

import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.models.dto import ChatRequest, ChatResponse, AnswerResponse
from app.models.schemas import CosmosMessage, CosmosSession, DataAgentRequest, Document
from app.services.cosmos_repo import CosmosDBRepository
from app.services.rag_service import RAGServiceFactory, format_context
from app.services.data_agent_client import FabricDataAgentClient
from app.core.errors import ChatbotError, ValidationError

logger = get_logger(__name__)


class ChatService:
    """Orchestrates chat interactions between user, history, RAG, and Data Agent."""
    
    def __init__(self):
        """Initialize chat service with dependencies."""
        self.cosmos_repo = CosmosDBRepository()
        self.rag_service = RAGServiceFactory.create_service()
        self.data_agent_client = FabricDataAgentClient(
            tenant_id=settings.tenant_id,
            data_agent_url=settings.data_agent_url,
            client_id=settings.client_id,
            client_secret=settings.client_secret
        )
    
    async def process_chat(self, request: ChatRequest, trace_id: str) -> ChatResponse:
        """Process a chat request end-to-end."""
        start_time = time.time()
        turn_id = str(uuid.uuid4())
        
        logger.info(
            f"Processing chat request for session {request.session_id}",
            extra={
                "session_id": request.session_id,
                "turn_id": turn_id,
                "message_length": len(request.message),
                "trace_id": trace_id
            }
        )
        
        try:
            # Step 1: Stateless mode - do not load history for agent context
            history = []
            
            # Step 2: Perform RAG if enabled
            retrieved_docs = []
            rag_context = ""
            if self.rag_service.is_available():
                retrieved_docs = await self.rag_service.retrieve(request.message)
                if retrieved_docs:
                    rag_context = format_context(retrieved_docs)
                    logger.info(
                        f"RAG retrieved {len(retrieved_docs)} documents",
                        extra={
                            "retrieved_count": len(retrieved_docs),
                            "context_length": len(rag_context)
                        }
                    )
            
            # Step 3: Build conversation messages
            messages = self._build_messages(
                request.message,
                history,
                rag_context,
                request.metadata
            )
            
            # Step 4: Call Fabric Data Agent
            agent_response = await self.data_agent_client.invoke_agent(
                messages=messages,
                context=rag_context if rag_context else None,
                thread_name=request.session_id  # Use session_id as thread name for persistence
            )
            
            # Step 5: Process response
            processed_response = self._process_agent_response(agent_response["response"])
            
            # Step 6: Persist messages
            await self._persist_messages(
                request.session_id,
                turn_id,
                request.message,
                processed_response.markdown,
                request.metadata
            )
            
            # Step 7: Build response
            latency_ms = round((time.time() - start_time) * 1000)
            
            response = ChatResponse(
                session_id=request.session_id,
                turn_id=turn_id,
                answer=processed_response,
                sources=[doc.to_source() for doc in retrieved_docs] if retrieved_docs else None,
                latency_ms=latency_ms,
                trace_id=trace_id
            )
            
            logger.info(
                f"Chat request completed successfully",
                extra={
                    "session_id": request.session_id,
                    "turn_id": turn_id,
                    "latency_ms": latency_ms,
                    "has_sources": len(retrieved_docs) > 0,
                    "trace_id": trace_id
                }
            )
            
            return response
            
        except Exception as e:
            latency_ms = round((time.time() - start_time) * 1000)
            logger.error(
                f"Chat processing failed for session {request.session_id}",
                extra={
                    "session_id": request.session_id,
                    "turn_id": turn_id,
                    "error": str(e),
                    "latency_ms": latency_ms,
                    "trace_id": trace_id
                },
                exc_info=True
            )
            raise
    
    async def _load_history(self, session_id: str) -> List[Dict[str, str]]:
        """Load conversation history for the session."""
        try:
            messages = await self.cosmos_repo.get_last_n_messages(
                session_id, 
                settings.max_history_turns
            )
            
            # Convert to agent format
            history = []
            for msg in messages:
                history.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            logger.debug(
                f"Loaded {len(messages)} messages for session {session_id}",
                extra={
                    "session_id": session_id,
                    "history_length": len(history)
                }
            )
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to load history for session {session_id}: {str(e)}")
            raise ChatbotError(f"Failed to load conversation history: {str(e)}")
    
    def _build_messages(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        rag_context: str,
        metadata: Optional[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Build conversation messages for the Fabric Data Agent."""
        # Build conversation messages
        messages = []
        
        # Add system message with instructions
        system_instructions = self._build_system_instructions(rag_context, metadata)
        messages.append({"role": "system", "content": system_instructions})
        
        # Add conversation history
        messages.extend(history)
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _build_system_instructions(
        self,
        rag_context: str,
        metadata: Optional[Dict[str, Any]]
    ) -> str:
        """Build system instructions for the Data Agent."""
        instructions = [
            "You are a helpful AI assistant for an enterprise chatbot application.",
            "Provide accurate, helpful responses based on the conversation context and any provided reference materials.",
            "Be concise but thorough in your responses.",
            "Use markdown formatting for better readability (headers, lists, bold, etc.).",
        ]
        
        if rag_context:
            instructions.append(
                "Below is context information that may be relevant to the user's query. "
                "Use this information to provide more accurate and grounded responses."
            )
        
        # Add any language-specific instructions
        if metadata and metadata.get("lang"):
            if metadata["lang"] != "en":
                instructions.append(f"Respond in {metadata['lang']} if possible.")
        
        return "\n\n".join(instructions)
    
    def _process_agent_response(self, response: str) -> AnswerResponse:
        """Process the agent response to create both plain text and markdown versions."""
        from app.models.dto import strip_markdown, clean_plain_text
        
        # Strip markdown for plain text version
        plain_text = clean_plain_text(strip_markdown(response))
        
        # Keep original response as markdown
        markdown = response.strip()
        
        return AnswerResponse(
            plain_text=plain_text,
            markdown=markdown
        )
    
    async def _persist_messages(
        self,
        session_id: str,
        turn_id: str,
        user_message: str,
        assistant_response: str,
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Persist both user and assistant messages to Cosmos DB."""
        try:
            # Create user message
            user_msg = CosmosMessage(
                session_id=session_id,
                role="user",
                content=user_message,
                metadata=metadata,
                turn_id=turn_id
            )
            
            # Create assistant message
            assistant_msg = CosmosMessage(
                session_id=session_id,
                role="assistant",
                content=assistant_response,
                metadata={"turn_id": turn_id},
                turn_id=turn_id
            )
            
            # Persist both messages
            await self.cosmos_repo.create_message(user_msg)
            await self.cosmos_repo.create_message(assistant_msg)

            # Update session metadata for session listing
            try:
                existing_session = await self.cosmos_repo.get_session(session_id)
                now = datetime.utcnow()
                if existing_session:
                    created_at = existing_session.created_at
                    message_count = existing_session.message_count + 2
                    user_id = existing_session.user_id
                else:
                    created_at = now
                    message_count = 2
                    user_id = metadata.get("userId") if metadata else None
                    if not user_id and metadata:
                        user_id = metadata.get("user_id")

                session = CosmosSession(
                    id=session_id,
                    user_id=user_id,
                    created_at=created_at,
                    last_active_at=now,
                    message_count=message_count,
                    metadata=metadata
                )
                await self.cosmos_repo.create_or_update_session(session)
            except Exception as e:
                logger.warning(f"Failed to update session metadata: {str(e)}")

            logger.debug(
                f"Persisted messages for turn {turn_id} in session {session_id}",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to persist messages: {str(e)}")
            # Don't fail the request if persistence fails, but log the error
    

    async def list_sessions(
        self,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List chat sessions for UI/session picker."""
        data = await self.cosmos_repo.list_sessions(limit=limit, offset=offset)
        sessions = data.get("sessions", [])
        total_count = data.get("total_count", len(sessions))
        has_more = (offset + len(sessions)) < total_count
        return {
            "sessions": sessions,
            "total_count": total_count,
            "has_more": has_more
        }

    async def create_session(
        self,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new session and persist metadata."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        session = CosmosSession(
            id=session_id,
            user_id=user_id,
            created_at=now,
            last_active_at=now,
            message_count=0,
            metadata=metadata
        )

        try:
            await self.cosmos_repo.create_or_update_session(session)
        except Exception as e:
            logger.warning(f"Failed to create session metadata: {str(e)}")

        return {
            "session_id": session_id,
            "created_at": now
        }

    async def get_session_history(
        self, 
        session_id: str, 
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get paginated history for a session."""
        try:
            messages = await self.cosmos_repo.get_session_messages(
                session_id, 
                limit=limit,
                offset=offset
            )
            
            # Convert to response format
            return [
                {
                    "id": msg.id,
                    "session_id": msg.session_id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                    "metadata": msg.metadata
                }
                for msg in messages
            ]
            
        except Exception as e:
            logger.error(f"Failed to get session history: {str(e)}")
            raise ChatbotError(f"Failed to retrieve session history: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all dependencies."""
        health_status = {
            "cosmos_db": await self._check_cosmos_health(),
            "rag_service": await self._check_rag_health(),
            "data_agent": await self._check_data_agent_health()
        }
        
        overall_healthy = all(health_status.values())
        
        return {
            "healthy": overall_healthy,
            "dependencies": health_status
        }
    
    async def _check_cosmos_health(self) -> bool:
        """Check Cosmos DB health."""
        try:
            return self.cosmos_repo.health_check()
        except Exception as e:
            logger.error(f"Cosmos DB health check failed: {str(e)}")
            return False
    
    async def _check_rag_health(self) -> bool:
        """Check RAG service health."""
        try:
            return self.rag_service.is_available()
        except Exception as e:
            logger.error(f"RAG service health check failed: {str(e)}")
            return False
    
    async def _check_data_agent_health(self) -> bool:
        """Check Fabric Data Agent health."""
        try:
            return self.data_agent_client.health_check()
        except Exception as e:
            logger.error(f"Data Agent health check failed: {str(e)}")
            return False
