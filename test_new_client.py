"""Quick test to verify the new Fabric Data Agent client works."""

import os
import sys
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env vars
from dotenv import load_dotenv
load_dotenv()

from app.services.data_agent_client import FabricDataAgentClient

async def test_client():
    """Test the client."""
    print("=== Testing Microsoft Fabric Data Agent Client ===\n")
    
    # Get credentials from env
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    data_agent_url = os.getenv("DATA_AGENT_URL")
    
    print(f"Tenant ID: {tenant_id}")
    print(f"Data Agent URL: {data_agent_url}")
    print(f"Client ID: {'Set' if client_id else 'Not set'}")
    print(f"Client Secret: {'Set' if client_secret else 'Not set'}")
    
    if not all([tenant_id, client_id, client_secret, data_agent_url]):
        print("\nMissing required environment variables!")
        return
    
    try:
        # Initialize client
        print("\nInitializing client...")
        client = FabricDataAgentClient(
            tenant_id=tenant_id,
            data_agent_url=data_agent_url,
            client_id=client_id,
            client_secret=client_secret
        )
        print("Client initialized successfully!")
        
        # Test authentication
        print("\nTesting authentication...")
        if client.health_check():
            print("Authentication successful!")
        else:
            print("Authentication failed!")
            return
        
        # Test a simple query
        print("\nTesting agent query...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, can you help me?"}
        ]
        
        response = await client.invoke_agent(
            messages=messages,
            thread_name="test-thread-123"
        )
        
        print(f"\nResponse status: {response.get('run_status')}")
        print(f"Thread ID: {response.get('thread_id')}")
        print(f"Response: {response.get('response', 'No response')[:200]}...")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_client())