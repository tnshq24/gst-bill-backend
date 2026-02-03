# Chatbot Avatar Backend

A production-ready FastAPI backend for chatbot avatar applications with Retrieval-Augmented Generation (RAG) and Microsoft Fabric Data Agent integration.

## Features

- **FastAPI**: Modern async web framework with automatic API documentation
- **Cosmos DB**: Scalable NoSQL database for conversation history persistence
- **RAG Support**: Configurable document retrieval with Azure AI Search or in-memory fallback
- **Fabric Data Agent**: Integration with Microsoft Fabric for grounded AI responses
- **Structured Logging**: JSON logging with trace IDs and performance metrics
- **Error Handling**: Comprehensive exception handling with detailed error responses
- **Health Monitoring**: Dependency health checks and monitoring endpoints
- **Type Safety**: Full type hints with Pydantic validation
- **Test Coverage**: Unit and integration tests for all components

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│   Frontend  │───▶│ FastAPI App  │───▶│ Chat Service│───▶│Cosmos DB     │
└─────────────┘    └─────┬────────┘    └─────┬───────┘    └──────────────┘
                          │                    │                            │
                          ▼                    ▼                            ▼
                 ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
                 │   RAG Service│    │Data Agent   │    │Azure AI      │
                 │              │    │Client       │    │Search (RAG)  │
                 └──────────────┘    └─────────────┘    └──────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Azure subscription with:
  - Cosmos DB (SQL API)
  - Azure AD service principal
  - Microsoft Fabric workspace (optional)

### Installation

1. **Clone and setup**:
```bash
git clone <repository-url>
cd gst-bill-chatbot-backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your actual Azure credentials and endpoints
```

3. **Run locally**:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $APP_PORT
```

4. **Access API docs**:
Open http://localhost:8000/docs for interactive API documentation.

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Azure AD service principal
CLIENT_ID="your-client-id"
TENANT_ID="your-tenant-id"
CLIENT_SECRET="your-client-secret"

# Fabric Data Agent
DATA_AGENT_URL="https://your-workspace.api.fabric.microsoft.com/aiassistant/openai"

# Cosmos DB
COSMOS_ENDPOINT="https://your-account.documents.azure.com:443/"
COSMOS_KEY="your-account-key"
COSMOS_DATABASE="chatdb"
COSMOS_CONTAINER="messages"

# Application settings
APP_ENV="dev"
APP_PORT=8000
MAX_HISTORY_TURNS=20
REQUEST_TIMEOUT_SECS=60

# RAG settings (set to "none" to disable)
RAG_PROVIDER="azure_ai_search"
AZURE_SEARCH_ENDPOINT="https://your-search.search.windows.net"
AZURE_SEARCH_KEY="your-search-key"
AZURE_SEARCH_INDEX="chat-docs"
RAG_TOP_K=5
```

### Key Settings

- `MAX_HISTORY_TURNS`: Number of conversation turns to include in context (default: 20)
- `RAG_TOP_K`: Number of documents to retrieve (default: 5)
- `REQUEST_TIMEOUT_SECS`: HTTP request timeout (default: 60)

## API Endpoints

### Chat

**POST /api/v1/chat**
Process a chat message and get AI response.

```json
{
  "sessionId": "user-session-123",
  "message": "What are our company policies on remote work?",
  "metadata": {
    "userId": "user-456",
    "lang": "en"
  }
}
```

**Response**:
```json
{
  "sessionId": "user-session-123",
  "turnId": "turn-789",
  "answer": {
    "plainText": "Here are our remote work policies...",
    "markdown": "## Remote Work Policies\n\nHere are our remote work policies..."
  },
  "sources": [
    {
      "title": "Remote Work Policy",
      "url": "https://company.com/policies/remote-work",
      "snippet": "Employees may work remotely up to 3 days per week..."
    }
  ],
  "latencyMs": 1245,
  "traceId": "trace-abc123"
}
```

### History

**GET /api/v1/sessions/{sessionId}/history?limit=20&offset=0**
Retrieve conversation history for a session.

### Health

**GET /api/v1/health**
Comprehensive health check with dependency status.

**GET /api/v1/healthz**
Simple health check for load balancers.

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_cosmos_repo.py
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .

# Type checking
mypy app/
```

### Project Structure

```
app/
├── api/
│   └── routes_chat.py          # API route handlers
├── core/
│   ├── config.py               # Environment configuration
│   ├── logging.py              # Structured logging setup
│   └── errors.py              # Custom exceptions and handlers
├── models/
│   ├── dto.py                  # API request/response models
│   └── schemas.py             # Database schemas
├── services/
│   ├── chat_service.py         # Main chat orchestration
│   ├── cosmos_repo.py          # Cosmos DB operations
│   ├── rag_service.py          # RAG document retrieval
│   └── data_agent_client.py   # Fabric Data Agent client
└── main.py                    # FastAPI application factory
```

## Deployment

### Local Development

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production (Gunicorn)

```bash
gunicorn -k uvicorn.workers.UvicornWorker -w 2 -c gunicorn.conf.py app.main:app
```

### Docker (Optional)

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Azure App Service

**Startup Command**:
```
gunicorn -k uvicorn.workers.UvicornWorker -w 2 -c gunicorn.conf.py app.main:app
```

**Application Settings** (set in Azure portal):
- `WEBSITES_PORT`: 8000
- All environment variables from `.env.example`

## Monitoring

### Health Checks

The application provides two health endpoints:
- `/api/v1/health` - Detailed health with dependency status
- `/api/v1/healthz` - Simple health check (returns 200/503)

### Logging

Logs are structured JSON with the following fields:
- `timestamp`: ISO format timestamp
- `level`: Log level (INFO, ERROR, etc.)
- `logger`: Logger name
- `message`: Log message
- `trace_id`: Request trace ID for correlation
- `session_id`: Chat session ID (when applicable)
- Additional context-specific fields

### Performance Monitoring

Key metrics to monitor:
- Request latency (included in chat responses)
- Error rates by endpoint
- Dependency health status
- Token usage from Fabric Data Agent

## Security

### Authentication

The service uses Azure AD service principal authentication for calling the Fabric Data Agent. Ensure:
- Client secret is stored securely (use Azure Key Vault in production)
- Minimum required permissions are granted
- Regular credential rotation

### Input Validation

- Message length limited to 4000 characters
- Session ID validation and sanitization
- CORS configuration for allowed origins

### Data Protection

- No logging of sensitive data or PII
- Tokens masked in logs
- Secure transmission (HTTPS) for all external calls

## Troubleshooting

### Common Issues

1. **Azure AD Token Errors**:
   - Verify client ID, tenant ID, and client secret
   - Check service principal permissions
   - Ensure correct resource URL in token scope

2. **Cosmos DB Connection Issues**:
   - Verify endpoint URL and account key
   - Check firewall rules
   - Validate database and container names

3. **RAG Service Errors**:
   - Verify Azure Search endpoint and key
   - Check index name and permissions
   - Try with `RAG_PROVIDER=none` to isolate the issue

4. **Fabric Data Agent Errors**:
   - Verify endpoint URL format
   - Check authentication scope
   - Review request payload structure

### Debug Mode

Set `LOG_LEVEL=DEBUG` in environment for detailed logging including:
- Full request/response payloads (sanitized)
- Dependency call details
- Trace propagation information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run `black` and `ruff` for code quality
5. Submit a pull request

## License

[Add your license information here]

## Support

For issues and questions:
- Check existing GitHub issues
- Review logs with trace ID from failed requests
- Contact the development team