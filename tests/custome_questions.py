#!/usr/bin/env python3
"""
Interactive CLI tester for FabricDataAgentClient.
- Reads TENANT_ID, DATA_AGENT_URL, CLIENT_ID, CLIENT_SECRET from env or .env.
- Type a question and press Enter; blank line exits.
- Use THREAD_NAME env var to pin to a specific thread (optional).
"""

import os
from app.services.data_agent_client import FabricDataAgentClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

def main():
    tenant_id = os.getenv("TENANT_ID")
    data_agent_url = os.getenv("DATA_AGENT_URL")
    client_id = os.getenv("CLIENT_ID") or os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET") or os.getenv("AZURE_CLIENT_SECRET")
    thread_name = os.getenv("THREAD_NAME")

    if not tenant_id or not data_agent_url:
        raise SystemExit("Set TENANT_ID and DATA_AGENT_URL in env or .env before running.")

    client = FabricDataAgentClient(
        tenant_id=tenant_id,
        data_agent_url=data_agent_url,
        client_id=client_id,
        client_secret=client_secret,
    )

    print("Fabric Data Agent CLI tester. Type a question and press Enter; blank line to quit.\n")
    while True:
        q = input("Question> ").strip()
        if not q:
            break
        try:
            reply = client.ask(q, thread_name=thread_name)
            print(f"\nReply:\n{reply}\n")
        except Exception as exc:
            print(f"Error: {exc}\n")

if __name__ == "__main__":
    main()
