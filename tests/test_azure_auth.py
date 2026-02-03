"""Diagnostic script to test Azure AD authentication."""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.identity import ClientSecretCredential
from app.core.config import settings

print("=== Azure AD Authentication Diagnostic ===\n")

# Check if credentials are set
print("1. Checking environment variables:")
print(f"   CLIENT_ID: {'Set' if settings.client_id else 'MISSING'}")
print(f"   TENANT_ID: {'Set' if settings.tenant_id else 'MISSING'}")
print(f"   CLIENT_SECRET: {'Set' if settings.client_secret else 'MISSING'}")
print(f"   DATA_AGENT_URL: {settings.data_agent_url}")

if not all([settings.client_id, settings.tenant_id, settings.client_secret]):
    print("\n❌ ERROR: Missing required credentials!")
    print("   Please check your .env file has all required variables.")
    sys.exit(1)

print("\n2. Testing token acquisition...")
try:
    credential = ClientSecretCredential(
        tenant_id=settings.tenant_id,
        client_id=settings.client_id,
        client_secret=settings.client_secret
    )
    
    # Try to get token
    print("   Requesting token for https://api.fabric.microsoft.com/.default...")
    token = credential.get_token("https://api.fabric.microsoft.com/.default")
    
    print(f"\n✅ SUCCESS!")
    print(f"   Token acquired (expires: {token.expires_on})")
    print(f"   Token prefix: {token.token[:50]}...")
    
except Exception as e:
    print(f"\n❌ FAILED!")
    print(f"   Error: {e}")
    print("\n3. Common causes:")
    print("   - Wrong CLIENT_ID, TENANT_ID, or CLIENT_SECRET")
    print("   - Service principal doesn't have Fabric permissions")
    print("   - Tenant doesn't allow service principal authentication")
    print("   - Network/firewall blocking Azure AD")
    sys.exit(1)