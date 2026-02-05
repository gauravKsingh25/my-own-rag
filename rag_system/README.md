# Production-Ready FastAPI RAG System Infrastructure

Enterprise-grade FastAPI infrastructure skeleton for a RAG (Retrieval-Augmented Generation) system.

## Features

- ✅ Async FastAPI application
- ✅ Structured JSON logging
- ✅ Request ID tracking middleware
- ✅ Custom exception handling
- ✅ PostgreSQL with async SQLAlchemy
- ✅ Redis async connection
- ✅ Celery background task processing
- ✅ Storage service abstraction (Local implementation)
- ✅ Pydantic settings management
- ✅ Health and readiness endpoints
- ✅ Docker and docker-compose setup
- ✅ Production-ready patterns

## Project Structure

```
rag_system/
├── app/
│   ├── api/                    # API endpoints
│   │   ├── __init__.py
│   │   └── health.py          # Health & readiness checks
│   ├── core/                   # Core functionality
│   │   ├── __init__.py
│   │   ├── config.py          # Pydantic settings
│   │   ├── logging.py         # Structured JSON logging
│   │   ├── middleware.py      # Request ID middleware
│   │   └── exceptions.py      # Custom exception handlers
│   ├── db/                     # Database connections
│   │   ├── __init__.py
│   │   ├── database.py        # Async SQLAlchemy
│   │   └── redis.py           # Redis async client
│   ├── services/               # Business logic services
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── base.py        # Storage abstraction
│   │   │   └── local.py       # Local file storage
│   │   └── __init__.py
│   ├── workers/                # Background tasks
│   │   ├── __init__.py
│   │   └── celery_app.py      # Celery configuration
│   ├── schemas/                # Pydantic models
│   │   ├── __init__.py
│   │   └── health.py
│   ├── __init__.py
│   └── main.py                 # FastAPI application
├── storage/                    # Local file storage
├── .env.example               # Environment variables template
├── .gitignore
├── docker-compose.yml         # Multi-container setup
├── Dockerfile                 # Application container
├── requirements.txt           # Python dependencies
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for containerized setup)

### Local Development

1. **Clone and navigate to the project:**
   ```bash
   cd rag_system
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run with Docker Compose (recommended):**
   ```bash
   docker-compose up --build
   ```

5. **Or run locally (requires PostgreSQL and Redis):**
   ```bash
   python -m app.main
   ```

6. **Access the application:**
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health
   - Readiness: http://localhost:8000/ready

### Run Celery Worker (if not using Docker)

```bash
celery -A app.workers.celery_app worker --loglevel=info
```

## API Endpoints

### Health Checks

- `GET /health` - Basic health check
- `GET /ready` - Comprehensive readiness check (database, Redis)

### Root

- `GET /` - API information

## Configuration

All configuration is managed through environment variables. See `.env.example` for available options:

- **Application**: Name, version, environment, debug mode
- **API**: Prefix, CORS origins, allowed hosts
- **Database**: PostgreSQL connection details
- **Redis**: Cache connection settings
- **Celery**: Task queue configuration
- **Storage**: File storage settings
- **Security**: Secret keys, token settings

## Storage Service

The `LocalStorageService` provides secure file storage with:

- **Path traversal protection**: Validates all user inputs
- **Auto-directory creation**: Creates necessary folders automatically
- **Async file operations**: Uses `aiofiles` for non-blocking I/O
- **Structured paths**: `storage/{user_id}/{doc_id}/{filename}`

Example usage:

```python
from app.services.storage import LocalStorageService

storage = LocalStorageService()
await storage.save_file(file_content, "user123", "doc456", "document.pdf")
```

## Logging

Structured JSON logging with:

- Request ID tracking
- Environment context
- Automatic log levels
- Correlation across services

Logs include: timestamp, level, logger name, request_id, app_name, environment, and custom fields.

## Docker Deployment

### Services

- **fastapi**: Main application (port 8000)
- **postgres**: PostgreSQL database (port 5432)
- **redis**: Redis cache (port 6379)
- **celery_worker**: Background task processor

### Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f fastapi

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up --build
```

## Development

### Adding New Endpoints

1. Create router in `app/api/`
2. Add schemas in `app/schemas/`
3. Register router in `app/main.py`

### Adding Background Tasks

1. Create task in `app/workers/`
2. Import in `app/workers/__init__.py`
3. Task will be auto-discovered by Celery

### Database Models

1. Create models using `app.db.database.Base`
2. Run migrations (add Alembic for production)

## Security Notes

- Change `SECRET_KEY` in production
- Use strong PostgreSQL passwords
- Configure Redis authentication in production
- Review CORS settings for production
- Use HTTPS in production
- Validate all user inputs

## Next Steps

This is an infrastructure skeleton. Add your RAG-specific features:

- Document upload endpoints
- Text chunking service
- Embedding generation
- Vector database integration
- Query endpoints
- Authentication/Authorization

## License

MIT

## Support

For issues and questions, please create an issue in the repository.
