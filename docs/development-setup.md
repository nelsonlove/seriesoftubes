# Development Setup Guide

This guide walks through setting up SeriesOfTubes for local development.

## Prerequisites

- Python 3.10+ 
- Docker & Docker Compose (for Redis and PostgreSQL)
- Node.js 18+ (for frontend development)

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/seriesoftubes.git
cd seriesoftubes

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev,api]"
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
# At minimum, set:
# - JWT_SECRET_KEY (or generate one)
# - OPENAI_API_KEY or ANTHROPIC_API_KEY
```

### 3. Start Services

```bash
# Start Redis and PostgreSQL
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 4. Initialize Database

```bash
# Run database migrations
alembic upgrade head

# The database will be created automatically
```

### 5. Start the API Server

```bash
# Development mode with auto-reload
uvicorn seriesoftubes.api.main:app --reload

# API will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### 6. Start the Frontend

#### Option A: Local Development (Recommended)

```bash
cd frontend
npm install
npm run dev

# Frontend will be available at http://localhost:5173
# Configure proxy in vite.config.ts or use VITE_API_URL env var
```

#### Option B: Docker Development with Hot Reload

```bash
# Start frontend with hot reload in Docker
docker-compose --profile dev up -d

# Frontend available at http://localhost:3000
# API available at http://localhost:8000
```

#### Option C: Production Build in Docker

```bash
# Build and run production frontend
docker-compose --profile prod up -d

# Frontend available at http://localhost
# API proxied through nginx at /api
```

## Service Configuration

### Redis (Caching)

By default, SeriesOfTubes uses in-memory caching. To use Redis:

1. Ensure Redis is running: `docker-compose ps`
2. Update `.tubes.yaml`:
   ```yaml
   cache:
     backend: redis
     enabled: true
   ```

Redis is recommended for:
- Multi-worker deployments
- Persistent cache across restarts
- Distributed execution

### PostgreSQL (Production Database)

For production-like development with PostgreSQL:

1. Update `.env`:
   ```bash
   DATABASE_URL=postgresql://seriesoftubes:development-password@localhost:5432/seriesoftubes
   ```

2. Run migrations:
   ```bash
   alembic upgrade head
   ```

### Using SQLite (Default)

SQLite is used by default for simplicity:
- Database file: `~/.seriesoftubes/db.sqlite`
- No additional setup required
- Good for single-user development

## Docker Development Options

### Option 1: Services Only (Recommended for Development)

Run only Redis and PostgreSQL in Docker, develop the app locally:

```bash
# Start only Redis and PostgreSQL
docker-compose up -d

# Run the API locally with hot-reload
uvicorn seriesoftubes.api.main:app --reload
```

### Option 2: Full Docker Stack

Run everything in Docker including the API:

```bash
# Build and start all services
docker-compose --profile with-api up -d

# View logs
docker-compose logs -f api

# Run CLI commands in container
docker-compose exec api s10s run workflow.yaml
```

### Option 3: Docker for Deployment Testing

Test production-like deployment:

```bash
# Build the image
docker build -t seriesoftubes:latest .

# Run with production config
docker run -d \
  --name seriesoftubes-api \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://..." \
  -e REDIS_URL="redis://..." \
  -e JWT_SECRET_KEY="..." \
  -e OPENAI_API_KEY="..." \
  seriesoftubes:latest
```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=seriesoftubes

# Run specific test file
pytest tests/test_engine.py -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
ruff check src/

# Run all checks (pre-commit)
pre-commit run --all-files
```

### Running Workflows

```bash
# Using CLI
s10s run examples/simple-test/workflow.yaml

# With inputs
s10s run workflow.yaml --inputs name="John" age=30

# Dry run (no external calls)
s10s test workflow.yaml --dry-run
```

## Docker Commands

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f redis
```

### Reset Data
```bash
# Stop and remove volumes
docker-compose down -v
```

## Production Setup

For production deployments:

1. Use `docker-compose.prod.yml`:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

2. Configure Redis authentication:
   - Set password in `redis.conf`
   - Update `REDIS_URL` in `.env`

3. Use PostgreSQL with SSL:
   ```bash
   DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
   ```

4. Enable security features:
   - Set strong `JWT_SECRET_KEY`
   - Configure `CORS_ORIGINS`
   - Enable file security restrictions

See [Security Guide](./security.md) for detailed production security configuration.

## Troubleshooting

### Redis Connection Failed

```bash
# Check Redis is running
docker-compose ps

# Test connection
redis-cli ping

# Check logs
docker-compose logs redis
```

### Database Migrations Failed

```bash
# Reset database (WARNING: deletes all data)
alembic downgrade base
alembic upgrade head
```

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Change API port
uvicorn seriesoftubes.api.main:app --port 8001
```

## Environment Variables

See `.env.example` for all available configuration options. Key variables:

- `JWT_SECRET_KEY`: Required for authentication
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`: LLM provider credentials
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string
- `CORS_ORIGINS`: Allowed frontend origins
- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)