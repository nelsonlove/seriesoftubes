# Docker Architecture & Port Guide

## Overview

SeriesOfTubes can run in multiple configurations, from simple local development to full production deployment.

## Port Mappings

### Default Ports

| Service | Container Port | Host Port | Access URL |
|---------|---------------|-----------|------------|
| Frontend (dev) | 5173 | 3000 | http://localhost:3000 |
| Frontend (prod) | 80 | 80 | http://localhost |
| API | 8000 | 8000 | http://localhost:8000 |
| PostgreSQL | 5432 | 5432 | localhost:5432 |
| Redis | 6379 | 6379 | localhost:6379 |

### Internal Docker Network

Within Docker, services communicate using service names:

| Service | Internal URL | Used By |
|---------|--------------|---------|
| api | http://api:8000 | Frontend nginx |
| postgres | postgres:5432 | API |
| redis | redis:6379 | API |

## Development Configurations

### 1. Minimal (Databases Only)

```bash
docker-compose up -d
```

- ✅ Redis at localhost:6379
- ✅ PostgreSQL at localhost:5432
- ❌ API (run locally)
- ❌ Frontend (run locally)

**Use when**: Developing with hot reload

### 2. Backend Development

```bash
docker-compose --profile with-api up -d
```

- ✅ Redis at localhost:6379
- ✅ PostgreSQL at localhost:5432
- ✅ API at localhost:8000
- ❌ Frontend (run locally)

**Use when**: Testing API in container

### 3. Full Stack Development with Hot Reload

```bash
docker-compose --profile dev up -d
```

- ✅ All services running
- ✅ Frontend with hot reload at localhost:3000
- ✅ API with hot reload at localhost:8000
- ✅ Databases available
- ✅ Code changes auto-reload both frontend and backend

**Use when**: Full stack development with hot reload

**How Hot Reload Works**:
- **Frontend**: Vite dev server watches for changes
- **Backend**: Uvicorn with --reload watches src/ directory
- **Volumes**: Only source code is mounted, not dependencies

### 4. Production Mode

```bash
docker-compose --profile prod --profile with-api up -d
```

- ✅ Frontend (nginx) at localhost:80
- ✅ API proxied through nginx
- ✅ All services production-ready

**Use when**: Testing production build

## How Frontend Connects to API

### Local Development (No Docker)

```
Browser → localhost:3000 (Vite) → Proxy → localhost:8000 (API)
```

Vite proxies `/api/*` requests to the API server.

### Docker Development Mode

```
Browser → localhost:3000 (Frontend Container) → localhost:8000 (API Container)
```

Frontend container makes direct requests to API.

### Docker Production Mode

```
Browser → localhost:80 (nginx) → /api/* → api:8000 (Internal)
                                → /* → Static files
```

Nginx serves static files and proxies API requests.

## Avoiding Port Conflicts

### Check What's Using Ports

```bash
# macOS/Linux
lsof -i :8000  # Check API port
lsof -i :5432  # Check PostgreSQL
lsof -i :6379  # Check Redis
lsof -i :3000  # Check frontend dev
lsof -i :80    # Check frontend prod

# All platforms
docker ps      # See running containers
```

### Change Ports If Needed

Edit `docker-compose.yml`:

```yaml
services:
  api:
    ports:
      - "8001:8000"  # API on 8001 instead
  
  postgres:
    ports:
      - "5433:5432"  # PostgreSQL on 5433
  
  redis:
    ports:
      - "6380:6379"  # Redis on 6380
```

Then update your `.env`:
```bash
DATABASE_URL=postgresql://user:pass@localhost:5433/db
REDIS_URL=redis://localhost:6380
```

## Common Issues & Solutions

### Frontend Can't Connect to API

**Local Development**:
- Check Vite proxy in `vite.config.ts`
- Ensure API is running on expected port

**Docker Development**:
- Check CORS_ORIGINS includes frontend URL
- Verify API health: `curl http://localhost:8000/health`

### Database Connection Failed

**From Host**:
```bash
DATABASE_URL=postgresql://seriesoftubes:development-password@localhost:5432/seriesoftubes
```

**From Container**:
```bash
DATABASE_URL=postgresql://seriesoftubes:development-password@postgres:5432/seriesoftubes
```

### Port Already in Use

**Option 1**: Stop conflicting service
```bash
# Find and kill process
lsof -i :8000
kill -9 <PID>
```

**Option 2**: Use different port
```bash
# Change in docker-compose.yml
ports:
  - "8001:8000"
```

## Network Isolation

Each Docker Compose project creates an isolated network:

- Network name: `seriesoftubes_default`
- Containers can't see other projects' containers
- Good for running multiple projects

### Connect Projects (If Needed)

```yaml
# In docker-compose.yml
networks:
  default:
    external:
      name: shared_network
```

## Production Best Practices

1. **Use Reverse Proxy**: Put nginx/traefik in front
2. **Bind to Localhost**: `127.0.0.1:8000:8000`
3. **Use Environment Files**: Never hardcode secrets
4. **Enable SSL**: Use Let's Encrypt with certbot
5. **Monitor Health**: Check `/health` endpoints

## Hot Reload Performance

### Backend Hot Reload

The backend uses Uvicorn's `--reload` flag which:
- Watches all Python files in `src/` directory
- Automatically restarts on changes
- Preserves database connections across reloads
- Typical reload time: 1-2 seconds

**Tips for Faster Reloads**:
1. Only mount necessary directories (src, tests, workflows)
2. Use `.dockerignore` to exclude large files
3. Dependencies are pre-installed in image (not reloaded)

### Frontend Hot Reload

The frontend uses Vite's HMR (Hot Module Replacement):
- Instant updates without full page reload
- Preserves component state during updates
- CSS changes apply immediately
- Typical update time: <100ms

### Troubleshooting Slow Reloads

If hot reload is slow:

1. **Check Volume Performance** (macOS):
   ```bash
   # Use delegated mode for better performance
   volumes:
     - ./src:/app/src:delegated
   ```

2. **Reduce Watched Files**:
   - Add large directories to `.dockerignore`
   - Don't mount `node_modules` or `.venv`

3. **Use Dev Images**:
   - Pre-install dependencies in Dockerfile.dev
   - Only mount source code, not entire project

## Quick Commands

```bash
# Start everything (dev mode with hot reload)
docker-compose --profile dev up -d

# Start minimal (just databases)
docker-compose up -d

# Production mode (no hot reload)
docker-compose --profile prod --profile with-api up -d

# Stop everything
docker-compose down

# Stop and remove data
docker-compose down -v

# View logs
docker-compose logs -f api-dev
docker-compose logs -f frontend-dev

# Enter container
docker-compose exec api-dev bash
docker-compose exec frontend-dev sh

# Run migrations
docker-compose exec api-dev alembic upgrade head

# Run CLI in container
docker-compose exec api-dev s10s run workflow.yaml

# Rebuild after dependency changes
docker-compose --profile dev build
```