# seriesoftubes
LLM Workflow Orchestration

## Project Overview

seriesoftubes is an LLM workflow orchestration platform that uses DAG-based YAML definitions to chain together API calls, LLM operations, and conditional routing. It's designed for developers who need to build complex data enrichment pipelines without the overhead of visual workflow builders.

**Core Philosophy**: Workflows are directed acyclic graphs (DAGs) of nodes. Each node does one thing well. Data flows explicitly between nodes. Everything is version-controlled YAML and Jinja2 templates.

## Key Commands

```bash
# Running workflows
s10s run workflow.yaml
s10s run workflow.yaml --inputs company="Acme Corp" location="Boston"
s10s list                          # List available workflows

# Development
pip install -e ".[dev]"            # Install with dev dependencies
s10s validate workflow.yaml        # Validate workflow structure
s10s test workflow.yaml --dry-run  # Test without executing external calls
```

## Architecture

### Core Concepts

1. **Nodes**: Individual units of computation (LLM calls, HTTP requests, routing logic)
2. **Dependencies**: Explicit DAG structure via `depends_on`
3. **Context**: Explicit data passing between nodes
4. **Templates**: Jinja2 templates for dynamic prompts

### Node Types (MVP)

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
fetch_fda:
  type: http
  depends_on: [classify_company]
  config:
    url: "https://api.fda.gov/drug/enforcement.json"
    method: GET  # default
    params:
      search: "{{ inputs.company_name }}"
    headers:
      Authorization: "Bearer {{ env.FDA_API_KEY }}"
```

**3. `route` Node**
```yaml
route_by_size:
  type: route
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
  depends_on: [fetch_fda, fetch_news, analyze_company]
  config:
    context:
      fda_data: fetch_fda
      news: fetch_news
      analysis: analyze_company
    prompt_template: "prompts/synthesis.j2"
```

In the Jinja2 template:
```jinja
# prompts/synthesis.j2
Based on the analysis:
{{ analysis.summary }}

FDA Compliance Issues:
{% for issue in fda_data.results %}
- {{ issue.report_date }}: {{ issue.reason }}
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

```yaml
# workflow.yaml
name: company-enrichment
version: 1.0
description: Enrich company data with FDA compliance and news

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
        Return size, industry, and whether it's FDA regulated.
      schema:
        size: enum[startup, smb, enterprise]
        industry: string
        fda_regulated: boolean

  # Parallel data fetching
  fetch_fda:
    type: http
    depends_on: [classify_company]
    config:
      context:
        company: classify_company
      url: "https://api.fda.gov/drug/enforcement.json"
      params:
        search: "{{ inputs.company_name }}"

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
        - when: classification.fda_regulated == true
          to: fda_analysis
        - default: standard_analysis

  # FDA-specific analysis
  fda_analysis:
    type: llm
    depends_on: [fetch_fda, fetch_news]
    config:
      context:
        fda_data: fetch_fda
        news: fetch_news
        classification: classify_company
      prompt_template: "prompts/fda-analysis.j2"

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
    depends_on: [fda_analysis, standard_analysis]
    config:
      context:
        analysis: _previous  # Special: gets output from whatever ran
      prompt: "Create an executive summary of this analysis: {{ analysis }}"

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

### Testing Strategy
```bash
# Dry run shows execution plan
s10s test workflow.yaml --dry-run

# Test with mocked external calls
s10s test workflow.yaml --mock-http --mock-llm
```

## Current Status

**Implemented:**
- Basic project structure with Hatchling build system
- CLI skeleton (`s10s`) with Typer
- FastAPI application skeleton at `/api`
- Development tooling (pytest, mypy, ruff, black)

**Not Yet Implemented:**
- Workflow execution engine
- Node types (llm, http, route)
- YAML parsing and validation
- Context resolution system
- Output storage

## Future Considerations (Post-MVP)

1. **Parallel Execution**: Use asyncio for parallel nodes
2. **Caching**: Redis/disk cache for expensive operations
3. **Streaming**: Server-sent events for real-time progress
4. **Enhanced Web UI**: Full dashboard beyond basic API
5. **Debugging**: Step-through debugger, node replay
6. **Hub**: Share/discover workflow templates

## Development Setup

```bash
# Clone and setup
git clone https://github.com/nelsonlove/seriesoftubes.git
cd seriesoftubes
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e ".[dev]"

# Configure
cp .tubes.example.yaml .tubes.yaml
# Edit .tubes.yaml with your API keys

# Run CLI
s10s --help
s10s run workflow.yaml  # Not implemented yet
s10s validate workflow.yaml  # Not implemented yet

# Run API server (basic skeleton exists)
pip install -e ".[api]"
uvicorn seriesoftubes.api.main:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs

# Run tests
pytest
mypy src/

# Development commands
hatch run test  # Run tests
hatch run lint:fmt  # Format code
hatch run lint:all  # Run all linters
```

### Pre-commit hooks

To enforce code formatting and type safety:

```bash
pip install -e ".[dev]"
pre-commit install
```

## Design Principles

1. **Explicit > Implicit**: All data flow is visible in YAML
2. **Composable**: Small nodes that do one thing well
3. **Version Control Friendly**: Everything is text files
4. **Fail Fast**: No silent failures or unclear states
5. **Developer First**: Built for engineers, not analysts

Remember: It's not a dump truck. It's a series of tubes.
