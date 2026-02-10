"""
Fabric Data Agent Client - Microsoft Implementation

A client for calling Microsoft Fabric Data Agents from outside
of the Fabric environment using service principal authentication.

Requirements:
- azure-identity
- openai
"""

import time
import uuid
import json
import os
import requests
import warnings
import asyncio
from typing import Optional, Dict, Any, List
from azure.identity import ClientSecretCredential
from openai import OpenAI


# Suppress OpenAI Assistants API deprecation warnings
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=r".*Assistants API is deprecated.*"
)


class FabricDataAgentClient:
    """
    Client for calling Microsoft Fabric Data Agents.
    
    This client handles:
    - Service principal authentication with Azure AD
    - Automatic token refresh
    - Bearer token management for API calls
    - Thread management for conversations
    """
    
    def __init__(
        self,
        tenant_id: str,
        data_agent_url: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize the Fabric Data Agent client.
        
        Args:
            tenant_id: Azure tenant ID
            data_agent_url: The published URL of the Fabric Data Agent
            client_id: Azure AD application (client) ID
            client_secret: Client secret for the service principal
        """
        self.tenant_id = tenant_id
        self.data_agent_url = data_agent_url
        self.credential = None
        self.token = None
        self.client_id = client_id
        self.client_secret = client_secret
        
        # Validate inputs
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not data_agent_url:
            raise ValueError("data_agent_url is required")
        if not client_id or not client_secret:
            raise ValueError("Both client_id and client_secret are required for service principal authentication")
        
        self._authenticate()
    
    def _authenticate(self):
        """Perform authentication and get initial token."""
        try:
            self.credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            # Get initial token
            self._refresh_token()
            
        except Exception as e:
            raise Exception(f"Authentication failed: {e}")
    
    def _refresh_token(self):
        """Refresh the authentication token."""
        try:
            if self.credential is None:
                raise ValueError("No credential available")
            self.token = self.credential.get_token("https://api.fabric.microsoft.com/.default")
        except Exception as e:
            raise Exception(f"Token refresh failed: {e}")
    
    def _get_openai_client(self) -> OpenAI:
        """Create an OpenAI client configured for Fabric Data Agent calls."""
        # Check if token needs refresh (refresh 5 minutes before expiry)
        if self.token and self.token.expires_on <= (time.time() + 300):
            self._refresh_token()
        
        if not self.token:
            raise ValueError("No valid authentication token available")
        
        return OpenAI(
            api_key="",  # Not used - we use Bearer token
            base_url=self.data_agent_url,
            default_query={"api-version": "2024-05-01-preview"},
            default_headers={
                "Authorization": f"Bearer {self.token.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "ActivityId": str(uuid.uuid4())
            }
        )

    def _get_or_create_thread(self, thread_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get an existing thread or create a new thread.
        
        Args:
            thread_name: Name for the thread. If None, creates new thread.
            
        Returns:
            Dict with thread id and name
        """
        if thread_name is None:
            thread_name = f'external-client-thread-{uuid.uuid4()}'
        
        # Build the private API URL for thread management
        if "aiskills" in self.data_agent_url:
            base_url = self.data_agent_url.replace("aiskills", "dataagents").removesuffix("/openai").replace("/aiassistant","/__private/aiassistant")
        else:
            base_url = self.data_agent_url.removesuffix("/openai").replace("/aiassistant","/__private/aiassistant")
        
        get_thread_url = f'{base_url}/threads/fabric?tag="{thread_name}"'

        headers = {
            "Authorization": f"Bearer {self.token.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "ActivityId": str(uuid.uuid4())
        }

        response = requests.get(get_thread_url, headers=headers)
        response.raise_for_status()
        thread = response.json()
        thread["name"] = thread_name

        return thread

    async def invoke_agent(
        self, 
        messages: List[Dict[str, str]], 
        context: Optional[str] = None,
        system_instructions: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        thread_name: Optional[str] = None,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Send messages to the Fabric Data Agent and get response.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            context: Optional context from RAG
            system_instructions: Optional system instructions
            temperature: Temperature for response generation
            max_tokens: Maximum tokens in response
            thread_name: Optional thread name for conversation persistence
            timeout: Maximum time to wait for response
            
        Returns:
            Dict with response and metadata
        """
        try:
            client = self._get_openai_client()
            
            # Create assistant
            assistant = client.beta.assistants.create(model="not used")
            
            # Get or create thread
            thread = self._get_or_create_thread(thread_name)
            
            # Add all messages to thread (only user and assistant roles supported)
            for msg in messages:
                role = msg['role']
                # Skip system messages as they're not supported by Fabric Data Agent
                if role == 'system':
                    continue
                # Ensure role is either 'user' or 'assistant'
                if role not in ['user', 'assistant']:
                    role = 'user'
                
                client.beta.threads.messages.create(
                    thread_id=thread['id'],
                    role=role,
                    content=msg['content']
                )
            
            # Start the run
            run = client.beta.threads.runs.create(
                thread_id=thread['id'],
                assistant_id=assistant.id
            )
            
            # Monitor the run with timeout
            start_time = time.time()
            while run.status in ["queued", "in_progress"]:
                if time.time() - start_time > timeout:
                    break
                
                time.sleep(2)
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread['id'],
                    run_id=run.id
                )
            
            # Get the response messages
            messages_response = client.beta.threads.messages.list(
                thread_id=thread['id'],
                order="asc"
            )

            # Extract the latest assistant response only
            def _extract_text(message) -> str:
                try:
                    content = message.content[0]
                    if hasattr(content, "text"):
                        text_content = getattr(content, "text", None)
                        if text_content is not None and hasattr(text_content, "value"):
                            return text_content.value
                        if text_content is not None:
                            return str(text_content)
                        return str(content)
                    return str(content)
                except (IndexError, AttributeError):
                    return str(message.content)

            assistant_messages = [
                msg for msg in messages_response.data if msg.role == "assistant"
            ]
            latest_response = _extract_text(assistant_messages[-1]) if assistant_messages else ""
            
            # Clean up resources
            try:
                client.beta.threads.delete(thread_id=thread['id'])
            except Exception:
                pass  # Ignore cleanup errors
            
            # Return the response
            full_response = latest_response or "No response received from the data agent."
            
            return {
                "response": full_response,
                "thread_id": thread['id'],
                "thread_name": thread['name'],
                "run_status": run.status,
                "usage": None,  # OpenAI assistants API doesn't return usage in same format
                "metadata": {
                    "timestamp": time.time(),
                    "timeout": timeout,
                    "success": run.status == "completed"
                }
            }
        
        except Exception as e:
            raise Exception(f"Error calling data agent: {e}")
    


    def ask(
        self,
        question: str,
        *,
        context: Optional[str] = None,
        system_instructions: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        thread_name: Optional[str] = None,
        timeout: int = 120,
    ) -> str:
        """Blocking helper for a single user question.

        If called from an active event loop, returns the coroutine so callers can await it.
        Otherwise runs the async flow and returns the response text.
        """
        payload = [
            {
                "role": "user",
                "content": question,
            }
        ]
        try:
            asyncio.get_running_loop()
            return self.invoke_agent(
                payload,
                context=context,
                system_instructions=system_instructions,
                temperature=temperature,
                max_tokens=max_tokens,
                thread_name=thread_name,
                timeout=timeout,
            )
        except RuntimeError:
            result = asyncio.run(
                self.invoke_agent(
                    payload,
                    context=context,
                    system_instructions=system_instructions,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    thread_name=thread_name,
                    timeout=timeout,
                )
            )
            return result.get("response", "")

    async def ask_async(
        self,
        question: str,
        *,
        context: Optional[str] = None,
        system_instructions: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        thread_name: Optional[str] = None,
        timeout: int = 120,
    ) -> str:
        """Async helper mirroring ask for callers already in an event loop."""
        payload = [
            {
                "role": "user",
                "content": question,
            }
        ]
        result = await self.invoke_agent(
            payload,
            context=context,
            system_instructions=system_instructions,
            temperature=temperature,
            max_tokens=max_tokens,
            thread_name=thread_name,
            timeout=timeout,
        )
        return result.get("response", "")

    def health_check(self) -> bool:
        """Check if the client can authenticate."""
        try:
            self._refresh_token()
            return True
        except Exception:
            return False
