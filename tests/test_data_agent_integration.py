# tests/test_data_agent_integration.py
import pytest
import os
from app.services.data_agent_client import FabricDataAgentClient
from app.models.schemas import DataAgentRequest

@pytest.mark.asyncio
async def test_real_fabric_data_agent():
    """Integration test - requires real credentials."""
    # This will use your actual .env credentials
    client = FabricDataAgentClient()
    
    request = DataAgentRequest(
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.7
    )
    
    response = await client.invoke_agent(request)
    assert response.response is not None
    print(f"Agent response: {response.response}")
