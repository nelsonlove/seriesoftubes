# seriesoftubes
LLM Workflow Orchestration

## Project Overview

seriesoftubes is an LLM workflow orchestration platform that uses DAG-based YAML definitions to chain together API calls, LLM operations, and conditional routing. It's designed for developers who need to build complex data enrichment pipelines without the overhead of visual workflow builders.

**Core Philosophy**: Workflows are directed acyclic graphs (DAGs) of nodes. Each node does one thing well. Data flows explicitly between nodes. Everything is version-controlled YAML and Jinja2 templates.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Set up configuration
cp .env.example .env
# Edit .env and add your API keys (OPENAI_API_KEY or ANTHROPIC_API_KEY)

# Start services with Docker (see Docker Setup section below)
docker-compose up -d               # Just databases (Redis + PostgreSQL + MinIO)
# OR
docker-compose --profile dev up -d # Full stack with hot reload

# Configure workflow settings (optional)
cp .tubes.example.yaml .tubes.yaml
# Edit .tubes.yaml to customize model, temperature, etc.

# Run example workflow
s10s run examples/simple-test/workflow.yaml --inputs company_name="OpenAI"

# See available workflows
s10s list
```

**Configuration**: See [docs/configuration-guide.md](docs/configuration-guide.md) for detailed configuration options.
**Docker Setup**: See the [Docker Setup](#docker-setup) section below for complete Docker instructions.
**Security**: See [docs/security.md](docs/security.md) for production security configuration.

## Key Commands

```bash
# Running workflows
s10s run workflow.yaml
s10s run workflow.yaml --inputs company="Acme Corp" location="Boston"
s10s list                          # List available workflows
s10s list -e ".*" -e "test/*"      # List with exclusions

# Testing workflows
s10s test workflow.yaml --dry-run  # Test without executing external calls

# Development
pip install -e ".[dev]"            # Install with dev dependencies
pytest                             # Run test suite
mypy src/                          # Type checking
pre-commit run --all-files         # Run all linters
```

## Features

### ✅ Implemented

- **11 Node Types**: LLM, HTTP, File, Python, Conditional, Split/Aggregate, Filter, Transform, Join, ForEach
- **Structured Output**: Pydantic schemas for LLM responses
- **Parallel Execution**: Split arrays and process in parallel
- **Template Engine**: Jinja2 templates with security levels
- **Python Execution**: RestrictedPython with 3 security levels
- **File Operations**: Read JSON, CSV, YAML, TXT, JSONL with security
- **Caching**: In-memory or Redis caching per node
- **API Server**: FastAPI with authentication
- **Web UI**: React frontend for workflow management
- **Docker Support**: Full stack with hot reload
- **Security**: JWT auth, CORS, file path validation, SSTI prevention

### 🚧 In Progress

- Message queue integration for distributed execution
- Object storage for large artifacts
- Workflow versioning and rollback
- Real-time execution monitoring

## Docker Setup

SeriesOfTubes includes comprehensive Docker support for both development and production environments.

### Docker Profiles

The project uses Docker Compose profiles to control which services start:

- **Default** (no profile): Only infrastructure services (PostgreSQL, Redis, MinIO)
- **`dev` profile**: Full development stack with hot reload
- **`prod` profile**: Production-ready frontend build
- **`with-api` profile**: Production API server (used with `prod`)

### Quick Start with Docker

```bash
# 1. Copy environment files
cp .env.example .env
cp .tubes.example.yaml .tubes.yaml

# 2. Edit .env and add your API keys (OPENAI_API_KEY or ANTHROPIC_API_KEY)

# 3. Start services based on your needs:

# Option A: Just infrastructure (PostgreSQL, Redis, MinIO)
docker-compose up -d

# Option B: Full development stack with hot reload
docker-compose --profile dev up -d

# Option C: Production stack
docker-compose --profile prod --profile with-api up -d
```

### Services Overview

| Service | Port | Description | Profiles |
|---------|------|-------------|----------|
| postgres | 5432 | PostgreSQL database | Always running |
| redis | 6379 | Redis cache | Always running |
| minio | 9000/9001 | S3-compatible storage (API/Console) | Always running |
| api-dev | 8000 | FastAPI with hot reload | `dev` |
| frontend-dev | 3000 | React with hot reload | `dev` |
| api | 8000 | FastAPI production | `with-api` |
| frontend | 80 | React production build | `prod` |

### Development Workflow

```bash
# Start development environment
docker-compose --profile dev up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs -f api-dev
docker-compose logs -f frontend-dev

# Access services
# - Frontend: http://localhost:3000
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)

# Stop all services
docker-compose --profile dev down

# Stop and remove volumes (clean slate)
docker-compose --profile dev down -v
```

### Custom Configuration

#### Custom Ports
```bash
# Use different ports if defaults are taken
FRONTEND_PORT=3001 API_PORT=8001 docker-compose --profile dev up -d
```

#### Environment Variables
The following environment variables can be configured in `.env`:
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `JWT_SECRET_KEY` - JWT secret (auto-generated for dev)
- `CORS_ORIGINS` - Allowed CORS origins
- `LOG_LEVEL` - Logging level (default: INFO)
- `API_PORT` - API port (default: 8000)
- `FRONTEND_PORT` - Frontend port (default: 3000)

### Production Deployment

```bash
# Build and start production services
docker-compose --profile prod --profile with-api up -d

# Production services run on:
# - Frontend: http://localhost (port 80)
# - API: http://localhost:8000

# Enable HTTPS with a reverse proxy (nginx example)
# See docs/deployment-guide.md for full production setup
```

### Docker Images

The project includes several Dockerfiles:

- `Dockerfile` - Multi-stage production API build
- `Dockerfile.dev` - Development API with hot reload
- `frontend/Dockerfile` - Production frontend build (nginx)
- `frontend/Dockerfile.dev` - Development frontend with Vite

### Troubleshooting Docker

#### Database Connection Issues
```bash
# Check if PostgreSQL is healthy
docker-compose ps postgres
docker-compose logs postgres

# Manually test connection
docker-compose exec postgres psql -U seriesoftubes -d seriesoftubes
```

#### API Not Starting
```bash
# Check API logs
docker-compose logs api-dev

# Common issues:
# - Missing .env file or API keys
# - Database not ready (wait for health checks)
# - Port already in use (change with API_PORT env var)
```

#### Frontend Can't Connect to API
```bash
# Ensure API is running
docker-compose ps api-dev

# Check CORS settings in docker-compose.yml
# Frontend uses VITE_API_PROXY_URL for container-to-container communication
```

#### Rebuilding After Code Changes
```bash
# Development mode auto-reloads, but if you change dependencies:
docker-compose --profile dev build --no-cache
docker-compose --profile dev up -d
```

### Data Persistence

Docker volumes persist data between container restarts:
- `postgres_data` - PostgreSQL database
- `redis_data` - Redis cache
- `minio_data` - Object storage files

To reset everything:
```bash
docker-compose down -v  # Removes all volumes
```

## Architecture

### Core Concepts

1. **Nodes**: Individual units of computation (LLM calls, HTTP requests, routing logic)
2. **Dependencies**: Explicit DAG structure via `depends_on`
3. **Context**: Explicit data passing between nodes
4. **Templates**: Jinja2 templates for dynamic prompts

### Node Types

Currently supported node types:
- `llm` - LLM API calls with structured output support
- `http` - HTTP/REST API calls
- `conditional` - Route execution based on conditions
- `file` - Read files (JSON, CSV, YAML, TXT, JSONL)
- `python` - Execute Python code with security levels
- `split` - Split arrays for parallel processing
- `aggregate` - Collect results from parallel executions
- `filter` - Filter arrays based on conditions
- `transform` - Transform data with Jinja2 templates
- `join` - Join data from multiple sources
- `foreach` - Iterate over arrays with subgraph execution

**1. `llm` Node**
```yaml
analyze_company:
  type: llm
  depends_on: [fetch_data]
  config:
    context:
      company_data: fetch_data
    prompt: "Analyze this company: {{ company_data }}"
    # Optional: structured extraction
    schema:
      risk_level: enum[low, medium, high]
      summary: string
```

**2. `http` Node**
```yaml
fetch_github:
  type: http
  depends_on: [classify_company]
  config:
    url: "https://api.github.com/search/repositories"
    method: GET  # default
    params:
      q: "{{ inputs.company_name }}"
      sort: "stars"
    headers:
      Accept: "application/vnd.github.v3+json"
```

**3. `conditional` Node** (formerly `route`)
```yaml
route_by_size:
  type: conditional
  depends_on: [classify_company]
  config:
    context:
      classification: classify_company
    routes:
      - when: classification.size == "enterprise"
        to: enterprise_flow
      - when: classification.size in ["smb", "startup"]
        to: standard_flow
      - default: standard_flow
```

### Data Flow

Data passes explicitly through context mappings:

```yaml
synthesize_report:
  type: llm
  depends_on: [fetch_github, fetch_news, analyze_company]
  config:
    context:
      github_data: fetch_github
      news: fetch_news
      analysis: analyze_company
    prompt_template: "prompts/synthesis.j2"
```

In the Jinja2 template:
```jinja
# prompts/synthesis.j2
Based on the analysis:
{{ analysis.summary }}

GitHub Activity:
{% for repo in github_data.items[:5] %}
- {{ repo.name }}: {{ repo.stargazers_count }} stars
{% endfor %}

Recent News:
{% for article in news.articles[:3] %}
- {{ article.title }} ({{ article.source }})
{% endfor %}
```

### File Structure

```
my-workflow/
├── workflow.yaml          # Main DAG definition
├── .tubes.yaml           # Config (API keys, models)
├── prompts/              # Jinja2 templates
│   ├── analyze.j2
│   ├── classify.j2
│   └── synthesize.j2
├── inputs/               # Default input files
│   └── companies.json
└── outputs/              # Execution results
    └── <execution-id>/
        ├── node-outputs.json
        └── final-output.json
```

### Example Workflow

A working example is provided in `examples/simple-test/workflow.yaml` that:
1. Classifies a company using an LLM
2. Fetches GitHub repositories for the company
3. Routes to different analysis paths based on company size
4. Generates a summary using the fetched data

Run it with: `s10s run examples/simple-test/workflow.yaml --inputs company_name="YourCompany"`

Here's a more complex example:

```yaml
# workflow.yaml
name: company-enrichment
version: 1.0
description: Enrich company data with GitHub activity and news

inputs:
  company_name:
    type: string
    required: true
  deep_analysis:
    type: boolean
    default: false

nodes:
  # First, classify the company
  classify_company:
    type: llm
    config:
      prompt: |
        Classify this company: {{ inputs.company_name }}
        Return size, industry, and whether it's a tech company.
      schema:
        size: enum[startup, smb, enterprise]
        industry: string
        is_tech: boolean

  # Parallel data fetching
  fetch_github_activity:
    type: http
    depends_on: [classify_company]
    config:
      context:
        company: classify_company
      url: "https://api.github.com/search/repositories"
      params:
        q: "{{ inputs.company_name }}"

  fetch_news:
    type: http
    depends_on: [classify_company]
    config:
      url: "https://newsapi.org/v2/everything"
      params:
        q: "{{ inputs.company_name }}"
        sortBy: "relevancy"
      headers:
        X-Api-Key: "{{ env.NEWS_API_KEY }}"

  # Route based on classification
  route_analysis:
    type: route
    depends_on: [classify_company]
    config:
      context:
        classification: classify_company
      routes:
        - when: classification.is_tech == true
          to: tech_analysis
        - default: standard_analysis

  # Tech-specific analysis
  tech_analysis:
    type: llm
    depends_on: [fetch_github_activity, fetch_news]
    config:
      context:
        github_data: fetch_github_activity
        news: fetch_news
        classification: classify_company
      prompt_template: "prompts/tech-analysis.j2"

  # Standard analysis
  standard_analysis:
    type: llm
    depends_on: [fetch_news]
    config:
      context:
        news: fetch_news
        classification: classify_company
      prompt_template: "prompts/standard-analysis.j2"

  # Final report (waits for whichever analysis ran)
  generate_report:
    type: llm
    depends_on: [tech_analysis, standard_analysis]
    config:
      context:
        # Note: route nodes return the selected path name, not the output
        # To get the actual output, reference the specific analysis nodes
        tech_result: tech_analysis
        standard_result: standard_analysis
      prompt: |
        Create an executive summary of the analysis.
        Tech analysis: {{ tech_result or "N/A" }}
        Standard analysis: {{ standard_result or "N/A" }}"

outputs:
  report: generate_report
  classification: classify_company
```

## Configuration

```yaml
# .tubes.yaml
llm:
  provider: openai  # or anthropic
  model: gpt-4
  api_key_env: OPENAI_API_KEY
  temperature: 0.7

http:
  timeout: 30
  retry_attempts: 3

execution:
  max_duration: 300  # 5 minutes
  save_intermediate: true
```

## MVP Scope

**Included:**
- Synchronous DAG execution (nodes run in dependency order)
- Three node types: `llm`, `http`, `route`
- Jinja2 templating for prompts
- Basic CLI interface
- YAML validation
- JSON output files

**Explicitly NOT Included (v1):**
- Parallel execution (even if DAG allows it)
- Retry/error recovery (fail fast)
- Caching
- Web UI
- Debugging tools beyond logs
- Streaming outputs
- Authentication beyond API keys
- Rate limiting
- Webhook triggers

## Implementation Notes

### Execution Engine
```python
# Pseudocode for the core engine
def execute_workflow(workflow, inputs):
    # 1. Validate DAG (no cycles)
    # 2. Topological sort nodes
    # 3. For each node in order:
    #    - Resolve context from dependencies
    #    - Execute node
    #    - Store output
    # 4. Return final outputs
```

### Node Execution
- Each node type has an executor class
- Executors handle context resolution and output formatting
- All data is JSON-serializable
- Large data should be referenced, not embedded
- Template context uses DotDict wrapper for safe dot notation (prevents `data.items` ambiguity)

### Testing Strategy
```bash
# Dry run shows execution plan
s10s test workflow.yaml --dry-run

# Verbose mode shows detailed output
s10s test workflow.yaml --dry-run --verbose
```

## Current Status

**Implemented:**
- ✅ Basic project structure with Hatchling build system
- ✅ Full CLI implementation with `run`, `list`, and `test` commands
- ✅ FastAPI application skeleton at `/api`
- ✅ Development tooling (pytest, mypy, ruff, black, pre-commit)
- ✅ Complete workflow execution engine with DAG validation
- ✅ All three node types (llm, http, route) with Jinja2 templating
- ✅ YAML parsing and validation with Pydantic v2
- ✅ Context resolution system with safe dot notation
- ✅ Output storage with JSON files per execution
- ✅ Configuration system with environment variable support
- ✅ Input validation with default values
- ✅ DotDict wrapper to prevent Jinja2 ambiguity

**Ready for Use:**
The MVP is fully functional! You can now create and run workflows with LLM calls, HTTP requests, and conditional routing.

## Future Considerations (Post-MVP)

1. **Parallel Execution**: Use asyncio for parallel nodes
2. **Caching**: Redis/disk cache for expensive operations
3. **Streaming**: Server-sent events for real-time progress
4. **Enhanced Web UI**: Full dashboard beyond basic API
5. **Debugging**: Step-through debugger, node replay
6. **Hub**: Share/discover workflow templates
7. **Tool-Using LLM Nodes**: Allow LLM nodes to act as agents with tool access

## Development Setup

### Quick Start

```bash
# Clone and setup
git clone https://github.com/nelsonlove/seriesoftubes.git
cd seriesoftubes

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run automated setup
chmod +x scripts/setup-dev.sh
./scripts/setup-dev.sh
```

### Manual Setup

1. **Install development dependencies:**
   ```bash
   pip install -e ".[dev,api]"
   ```

2. **Install pre-commit hooks:**
   ```bash
   pre-commit install
   pre-commit install --hook-type commit-msg
   ```

3. **Configure API keys:**
   ```bash
   cp .tubes.example.yaml .tubes.yaml
   # Edit .tubes.yaml with your API keys
   ```

4. **Verify setup:**
   ```bash
   pre-commit run --all-files
   ```

### How Pre-commit Works

Our pre-commit configuration uses **local hooks** that run tools from your Python environment. This means:

- ✅ No version conflicts between pre-commit and your environment
- ✅ No duplicate dependency specifications
- ✅ Faster execution (no isolated environments)
- ✅ Easier debugging (same environment as manual runs)

### Available Commands

```bash
# CLI commands
s10s --help
s10s run examples/simple-test/workflow.yaml --inputs company_name="OpenAI"
s10s list
s10s test examples/simple-test/workflow.yaml --dry-run

# API server
uvicorn seriesoftubes.api.main:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs

# Testing and linting
pytest                      # Run tests
mypy src/                   # Type checking
black src/ tests/           # Format code
ruff check --fix src/ tests/  # Lint and fix
pre-commit run --all-files  # Run all checks

# Hatch commands
hatch run test              # Run tests
hatch run lint:fmt          # Format code
hatch run lint:all          # Run all linters
```

### Troubleshooting

#### "command not found" errors
Make sure you've activated your virtual environment and installed dev dependencies:
```bash
source venv/bin/activate
pip install -e ".[dev]"
```

#### Mypy errors about missing imports
Install API dependencies if checking API code:
```bash
pip install -e ".[api]"
```

#### Skipping hooks temporarily
```bash
git commit --no-verify -m "Emergency fix"
```
⚠️ Use sparingly - hooks exist to maintain code quality!

### Updating Tools

Since we use local hooks, updating tools is simple:
```bash
# Update all dev tools
pip install -e ".[dev]" --upgrade

# Update specific tool
pip install --upgrade mypy==1.13.0
```

No need to update `.pre-commit-config.yaml` - it automatically uses whatever version is installed!

## Design Principles

1. **Explicit > Implicit**: All data flow is visible in YAML
2. **Composable**: Small nodes that do one thing well
3. **Version Control Friendly**: Everything is text files
4. **Fail Fast**: No silent failures or unclear states
5. **Developer First**: Built for engineers, not analysts

Remember: It's not a dump truck. It's a series of tubes.
