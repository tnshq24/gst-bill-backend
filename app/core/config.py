"""Application configuration with environment variable validation."""

import os
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Azure AD service principal
    client_id: str = Field(..., description="Azure AD client ID")
    tenant_id: str = Field(..., description="Azure AD tenant ID")
    client_secret: str = Field(..., description="Azure AD client secret")
    
    # Fabric Data Agent
    data_agent_url: str = Field(..., description="Fabric Data Agent endpoint URL")
    
    # Cosmos DB
    cosmos_endpoint: str = Field(..., description="Cosmos DB endpoint URL")
    cosmos_key: str = Field(..., description="Cosmos DB account key")
    cosmos_database: str = Field(default="chatdb", description="Cosmos DB database name")
    cosmos_container: str = Field(default="messages", description="Cosmos DB container name")
    
    # App settings
    app_env: str = Field(default="dev", description="Application environment")
    app_port: int = Field(default=8000, description="Application port")
    max_history_turns: int = Field(default=20, description="Maximum number of conversation turns to load")
    request_timeout_secs: int = Field(default=60, description="Request timeout in seconds")
    
    # RAG settings
    rag_provider: str = Field(default="azure_ai_search", description="RAG provider to use")
    azure_search_endpoint: Optional[str] = Field(None, description="Azure AI Search endpoint")
    azure_search_key: Optional[str] = Field(None, description="Azure AI Search key")
    azure_search_index: str = Field(default="chat-docs", description="Azure AI Search index name")
    rag_top_k: int = Field(default=5, description="Number of documents to retrieve from RAG")
    
    
    # Security
    cors_origins: str = Field(default="http://localhost:3000", description="CORS allowed origins as comma-separated string")
    max_message_length: int = Field(default=4000, description="Maximum message length")

    # Auth / JWT
    api_client_id: Optional[str] = Field(None, description="Client ID for token endpoint")
    api_client_secret: Optional[str] = Field(None, description="Client secret for token endpoint")
    jwt_secret: Optional[str] = Field(None, description="JWT signing secret")
    jwt_issuer: str = Field(default="chatbot-backend", description="JWT issuer")
    jwt_audience: str = Field(default="chatbot-clients", description="JWT audience")
    jwt_exp_minutes: int = Field(default=60, description="JWT expiration in minutes")
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list."""
        if not self.cors_origins:
            return ["http://localhost:3000"]
        origins = [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]
        return origins if origins else ["http://localhost:3000"]
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "validate_assignment": True,
    }
    
    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"
    
    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


# Global settings instance - created lazily to allow environment variables to be loaded first
_settings_instance: Optional[Settings] = None

def get_settings() -> Settings:
    """Get or create settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance

# Module-level settings accessor - use this for lazy loading
class _SettingsProxy:
    """Proxy class to delay settings instantiation until first access."""
    def __getattr__(self, name: str):
        return getattr(get_settings(), name)
    
    def __setattr__(self, name: str, value):
        return setattr(get_settings(), name, value)

# Create proxy instance - this won't actually instantiate Settings until accessed
settings = _SettingsProxy()
