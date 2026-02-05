"""Cosmos DB repository for chat message and session persistence."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from azure.cosmos import CosmosClient, PartitionKey, ContainerProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError, CosmosHttpResponseError

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import CosmosMessage, CosmosSession
from app.core.errors import CosmosDBError

logger = get_logger(__name__)


class CosmosDBRepository:
    """Repository for Cosmos DB operations with chat messages and sessions."""
    
    def __init__(self):
        """Initialize Cosmos DB client and containers."""
        self.client = None
        self.messages_container = None
        self.sessions_container = None
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize Cosmos DB client and get container references."""
        try:
            self.client = CosmosClient(
                url=settings.cosmos_endpoint,
                credential=settings.cosmos_key
            )
            
            # Get database
            database = self.client.get_database_client(settings.cosmos_database)
            
            # Get containers
            self.messages_container = database.get_container_client(settings.cosmos_container)
            
            # Optional sessions container
            try:
                self.sessions_container = database.get_container_client("sessions")
                self.sessions_container.read()
            except (CosmosResourceNotFoundError, CosmosHttpResponseError):
                try:
                    self.sessions_container = database.create_container_if_not_exists(
                        id="sessions",
                        partition_key=PartitionKey(path="/id")
                    )
                    logger.info("Sessions container created")
                except Exception:
                    logger.warning("Sessions container not available, session metadata will not be persisted", exc_info=True)
                    self.sessions_container = None
            
            logger.info("Cosmos DB repository initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB: {str(e)}", exc_info=True)
            raise CosmosDBError("Failed to initialize Cosmos DB client", {"original_error": str(e)})
    
    async def create_message(self, message: CosmosMessage) -> CosmosMessage:
        """Create a new message in Cosmos DB."""
        try:
            message_dict = message.to_dict()
            if self.messages_container is None:
                raise CosmosDBError("Messages container not initialized")
            self.messages_container.create_item(body=message_dict)
            
            logger.info(
                f"Created message: {message.id}",
                extra={
                    "message_id": message.id,
                    "session_id": message.session_id,
                    "role": message.role
                }
            )
            
            return message
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to create message: {str(e)}", exc_info=True)
            raise CosmosDBError(f"Failed to create message: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating message: {str(e)}", exc_info=True)
            raise CosmosDBError(f"Unexpected error creating message: {str(e)}")

    async def list_sessions(
        self,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List chat sessions with last activity and message counts."""
        if not self.sessions_container:
            logger.warning("Sessions container not available; returning empty session list")
            return {"sessions": [], "total_count": 0}

        try:
            query = f"""
            SELECT c.id, c.lastActiveAt, c.messageCount
            FROM c
            ORDER BY c.lastActiveAt DESC
            OFFSET {offset} LIMIT {limit}
            """

            items = list(self.sessions_container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))

            sessions = [
                {
                    "session_id": item.get("id"),
                    "last_active_at": item.get("lastActiveAt"),
                    "message_count": int(item.get("messageCount", 0) or 0)
                }
                for item in items
                if item.get("id")
            ]

            count_query = "SELECT VALUE COUNT(1) FROM c"
            count_result = list(self.sessions_container.query_items(
                query=count_query,
                enable_cross_partition_query=True
            ))
            total_count = int(count_result[0]) if count_result else 0

            return {
                "sessions": sessions,
                "total_count": total_count
            }
        except CosmosResourceNotFoundError:
            logger.warning("Sessions container not found; returning empty session list")
            return {"sessions": [], "total_count": 0}
        except CosmosHttpResponseError as e:
            if getattr(e, "status_code", None) == 404:
                logger.warning("Sessions container not found; returning empty session list")
                return {"sessions": [], "total_count": 0}
            logger.error(f"Failed to list sessions: {str(e)}", exc_info=True)
            raise CosmosDBError(f"Failed to list sessions: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to list sessions: {str(e)}", exc_info=True)
            raise CosmosDBError(f"Failed to list sessions: {str(e)}")

    async def get_session_messages(
        self, 
        session_id: str, 
        limit: int = 20,
        offset: int = 0
    ) -> List[CosmosMessage]:
        """Retrieve messages for a session with pagination."""
        try:
            # Query parameters
            query = f"""
            SELECT * FROM c WHERE c.sessionId = @session_id 
            ORDER BY c.createdAt DESC
            OFFSET {offset} LIMIT {limit}
            """
            
            parameters: List[Dict[str, Any]] = [  # type: ignore
                {"name": "@session_id", "value": session_id}
            ]
            
            # Execute query
            if self.messages_container is None:
                raise CosmosDBError("Messages container not initialized")
            items = list(self.messages_container.query_items(
                query=query,
                parameters=parameters,  # type: ignore
                partition_key=session_id
            ))
            
            # Convert to CosmosMessage objects and restore chronological order
            messages = [CosmosMessage.from_dict(item) for item in items]
            messages.reverse()  # Reverse to get chronological order
            
            logger.info(
                f"Retrieved {len(messages)} messages for session {session_id}",
                extra={
                    "session_id": session_id,
                    "message_count": len(messages),
                    "limit": limit,
                    "offset": offset
                }
            )
            
            return messages
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to retrieve messages for session {session_id}: {str(e)}", exc_info=True)
            raise CosmosDBError(f"Failed to retrieve messages: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error retrieving messages: {str(e)}", exc_info=True)
            raise CosmosDBError(f"Unexpected error retrieving messages: {str(e)}")
    
    async def get_last_n_messages(
        self, 
        session_id: str, 
        n: int = 20
    ) -> List[CosmosMessage]:
        """Retrieve the last N messages for a session (for context)."""
        return await self.get_session_messages(session_id, limit=n)
    
    async def count_session_messages(self, session_id: str) -> int:
        """Count total messages in a session."""
        try:
            if self.messages_container is None:
                raise CosmosDBError("Messages container not initialized")
            query = """
            SELECT VALUE COUNT(1) FROM c WHERE c.sessionId = @session_id
            """
            
            parameters: List[Dict[str, Any]] = [  # type: ignore
                {"name": "@session_id", "value": session_id}
            ]
            
            result = list(self.messages_container.query_items(
                query=query,
                parameters=parameters,
                partition_key=session_id
            ))
            
            count = result[0] if isinstance(result[0], int) else int(result[0]) if result and isinstance(result[0], (str, float)) else 0 if result else 0
            
            logger.debug(
                f"Counted {count} messages for session {session_id}",
                extra={
                    "session_id": session_id,
                    "count": count
                }
            )
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to count messages for session {session_id}: {str(e)}", exc_info=True)
            return 0
    
    async def create_or_update_session(self, session: CosmosSession) -> CosmosSession:
        """Create or update session metadata."""
        if not self.sessions_container:
            logger.debug("Sessions container not available, skipping session persistence")
            return session
        
        try:
            session_dict = session.to_dict()
            self.sessions_container.upsert_item(body=session_dict)
            
            logger.info(
                f"Upserted session: {session.id}",
                extra={
                    "session_id": session.id,
                    "user_id": session.user_id,
                    "message_count": session.message_count
                }
            )
            
            return session
            
        except CosmosHttpResponseError as e:
            logger.error(f"Failed to upsert session {session.id}: {str(e)}", exc_info=True)
            raise CosmosDBError(f"Failed to upsert session: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error upserting session: {str(e)}", exc_info=True)
            raise CosmosDBError(f"Unexpected error upserting session: {str(e)}")
    
    async def get_session(self, session_id: str) -> Optional[CosmosSession]:
        """Retrieve session metadata."""
        if not self.sessions_container:
            return None
        
        try:
            try:
                item = self.sessions_container.read_item(
                    item=session_id,
                    partition_key=session_id
                )
                return CosmosSession.from_dict(item)
                
            except CosmosResourceNotFoundError:
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id}: {str(e)}", exc_info=True)
            return None
    
    async def delete_session_messages(self, session_id: str) -> int:
        """Delete all messages for a session. Returns number of deleted messages."""
        try:
            # Get all messages first
            messages = await self.get_session_messages(session_id, limit=1000)
            
            deleted_count = 0
            for message in messages:
                try:
                    if self.messages_container is None:
                        raise CosmosDBError("Messages container not initialized")
                    self.messages_container.delete_item(
                        item=message.id,
                        partition_key=session_id
                    )
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete message {message.id}: {str(e)}")
            
            logger.info(
                f"Deleted {deleted_count} messages for session {session_id}",
                extra={
                    "session_id": session_id,
                    "deleted_count": deleted_count
                }
            )
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete messages for session {session_id}: {str(e)}", exc_info=True)
            raise CosmosDBError(f"Failed to delete messages: {str(e)}")
    
    def health_check(self) -> bool:
        """Check if Cosmos DB connection is healthy."""
        try:
            if self.client is None:
                return False
            # Simple health check - try to read database properties
            database = self.client.get_database_client(settings.cosmos_database)
            database.read()
            return True
        except Exception as e:
            logger.error(f"Cosmos DB health check failed: {str(e)}")
            return False