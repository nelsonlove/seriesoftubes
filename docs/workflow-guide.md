# SeriesOfTubes Workflow Guide

This guide provides comprehensive documentation for creating and understanding SeriesOfTubes workflow definitions.

## Table of Contents

1. [Overview](#overview)
2. [Workflow Structure](#workflow-structure)
3. [Node Types](#node-types)
4. [Template System](#template-system)
5. [Context and Data Flow](#context-and-data-flow)
6. [Complete Examples](#complete-examples)
7. [Best Practices](#best-practices)

## Overview

SeriesOfTubes workflows are defined in YAML files that describe a directed acyclic graph (DAG) of operations. Each
workflow consists of:

- **Inputs**: Parameters passed to the workflow
- **Nodes**: Individual operations that process data
- **Outputs**: Final results from the workflow

## Workflow Structure

### Basic Structure

```yaml
name: My Workflow
description: A detailed description of what this workflow does
version: 1.0.0

inputs:
  required: [param1, param2]
  schema:
    param1:
      type: string
      description: First parameter
    param2:
      type: number
      default: 42

nodes:
  node_name:
    type: node_type
    depends_on: [other_node]
    config:
      # Node-specific configuration

outputs:
  mapping:
    result: final_node
```

### Top-Level Fields

#### `name` (required)

Human-readable name for the workflow.

```yaml
name: Company Enrichment Pipeline
```

#### `description` (optional)

Detailed description of the workflow's purpose and functionality.

```yaml
description: |
  Enriches company data by fetching information from multiple sources,
  classifying the company, and generating a comprehensive analysis.
```

#### `version` (optional)

Semantic version of the workflow (default: "1.0.0").

```yaml
version: 2.1.0
```

#### `inputs` (optional)

Defines workflow input parameters.

```yaml
inputs:
  required: [company_name]  # List of required parameter names
  schema:
    company_name:
      type: string
      description: Name of the company to analyze
    include_github:
      type: boolean
      default: true
      description: Whether to search GitHub
    max_results:
      type: number
      default: 10
      description: Maximum number of results to fetch
```

#### `nodes` (required)

The DAG nodes that make up the workflow. Each node has a unique name and configuration.

```yaml
nodes:
  fetch_data:
    type: http
    config:
      url: https://api.example.com/company/{{ inputs.company_name }}

  analyze:
    type: llm
    depends_on: [fetch_data]
    config:
      context:
        data: fetch_data
      prompt: Analyze this company data: {{ data }}
```

#### `outputs` (optional)

Defines the workflow's output structure.

```yaml
outputs:
  mapping:
    company_info: classify_company
    analysis: final_analysis
  schema:
    company_info:
      type: object
    analysis:
      type: string
```

## Node Types

SeriesOfTubes supports four node types, each designed for specific operations.

### LLM Node

Calls a language model for text generation, analysis, or structured extraction.

```yaml
analyze_company:
  type: llm
  depends_on: [fetch_data]
  config:
    # Provider configuration
    provider: openai  # or anthropic
    model: gpt-4
    temperature: 0.7
    max_tokens: 1000

    # Context from other nodes
    context:
      company_data: fetch_data
      classification: classify_company

    # Prompt (inline or external)
    prompt: |
      Analyze this company:
      Name: {{ inputs.company_name }}
      Data: {{ company_data }}
      Classification: {{ classification }}

    # OR use external template
    # prompt_template: prompts/analysis.j2

    # Optional: structured extraction
    schema:
      summary: string
      key_findings:
        type: array
        items: string
      recommendation: string
```

#### LLM Node Configuration

- **`provider`**: LLM provider (`openai` or `anthropic`)
- **`model`**: Model identifier (e.g., `gpt-4`, `claude-3-opus-20240229`)
- **`prompt`**: Inline prompt template (Jinja2)
- **`prompt_template`**: Path to external prompt template file
- **`context`**: Map variables from other nodes
- **`schema`**: JSON schema for structured extraction
- **`temperature`**: LLM temperature (0-2, default: 0.7)
- **`max_tokens`**: Maximum response tokens

### HTTP Node

Makes HTTP API calls with support for authentication and templating.

```yaml
fetch_github:
  type: http
  config:
    url: https://api.github.com/search/repositories
    method: GET
    headers:
      Accept: application/vnd.github.v3+json
      Authorization: Bearer {{ env.GITHUB_TOKEN }}
    params:
      q: "org:{{ inputs.company_name }}"
      sort: stars
      per_page: 10

    # Optional authentication
    auth:
      type: bearer
      token: "{{ env.GITHUB_TOKEN }}"
```

#### HTTP Node Configuration

- **`url`**: Endpoint URL (supports Jinja2 templates)
- **`method`**: HTTP method (GET, POST, PUT, DELETE, PATCH)
- **`headers`**: Request headers (supports templates)
- **`body`**: Request body for POST/PUT requests
- **`params`**: Query parameters for GET requests
- **`auth`**: Authentication configuration
    - `type`: `bearer`, `basic`, or `api_key`
    - `token`: Auth token (supports env vars)
    - `header`: Header name for API key auth

### Route Node

Conditional routing based on data evaluation.

```yaml
route_by_size:
  type: route
  depends_on: [classify_company]
  config:
    context:
      company: classify_company
    routes:
      - condition: company.size == "enterprise"
        output:
          template: enterprise_analysis
          priority: high
      - condition: company.size == "startup"
        output:
          template: startup_analysis
          priority: medium
    default:
      template: generic_analysis
      priority: low
```

#### Route Node Configuration

- **`context`**: Map variables from other nodes
- **`routes`**: Array of routing rules
    - `condition`: Jinja2 expression that evaluates to boolean
    - `output`: Value to output if condition is true
- **`default`**: Output if no conditions match

### File Node

Reads and parses files in various formats.

```yaml
load_companies:
  type: file
  config:
    path: "{{ inputs.data_file }}"
    format: auto  # or json, csv, yaml, txt, pdf, docx, xlsx, html

    # CSV-specific options
    csv_options:
      delimiter: ","
      has_header: true
```

#### File Node Configuration

- **`path`**: File path (supports Jinja2 templates)
- **`format`**: File format (auto-detected by default)
- **`encoding`**: Text encoding (default: utf-8)
- **`csv_options`**: CSV parsing options
    - `delimiter`: Column delimiter
    - `has_header`: Whether first row contains headers

## Template System

SeriesOfTubes uses Jinja2 for templating throughout the workflow.

### Available Variables

Templates have access to:

1. **`inputs`**: All workflow inputs
2. **`env`**: Environment variables
3. **Context variables**: Data from other nodes via `context` mapping

### Template Examples

#### Basic Variable Access

```yaml
prompt: |
  Company: {{ inputs.company_name }}
  Location: {{ inputs.location | default("Unknown") }}
```

#### Accessing Node Outputs

```yaml
context:
  data: fetch_data
  analysis: analyze_company
prompt: |
  Previous analysis: {{ analysis.summary }}
  Raw data: {{ data }}
```

#### Using Filters

```yaml
prompt: |
  Found {{ repos.items | length }} repositories
  Top repo: {{ repos.items[0].name | upper }}
```

#### Conditional Logic

```yaml
prompt: |
  {% if company.public %}
  This is a public company listed on {{ company.exchange }}.
  {% else %}
  This is a private company.
  {% endif %}
```

#### Loops

```yaml
prompt: |
  Key products:
  {% for product in company.products %}
  - {{ product.name }}: {{ product.description }}
  {% endfor %}
```

### External Prompt Templates

For complex prompts, use external template files:

```yaml
analyze:
  type: llm
  config:
    prompt_template: prompts/analysis.j2
    context:
      data: fetch_data
```

Create `prompts/analysis.j2`:

```jinja2
You are analyzing {{ inputs.company_name }}.

## Company Data
{{ data | tojson(indent=2) }}

## Task
Provide a comprehensive analysis focusing on:
1. Market position
2. Technology stack
3. Growth potential

{% if inputs.include_competitors %}
Also compare with major competitors.
{% endif %}
```

## Context and Data Flow

### Explicit Dependencies

Nodes must explicitly declare dependencies:

```yaml
nodes:
  fetch_data:
    type: http
    config:
      url: https://api.example.com/data

  process_data:
    type: llm
    depends_on: [fetch_data]  # Must wait for fetch_data
    config:
      context:
        raw_data: fetch_data  # Maps fetch_data output to 'raw_data'
      prompt: Process this data: {{ raw_data }}
```

### Context Mapping

The `context` field maps node outputs to template variables:

```yaml
final_analysis:
  type: llm
  depends_on: [classify, enrich, analyze]
  config:
    context:
      classification: classify      # classify output → classification variable
      enrichment: enrich           # enrich output → enrichment variable
      analysis: analyze            # analyze output → analysis variable
    prompt: |
      Classification: {{ classification }}
      Enrichment data: {{ enrichment }}
      Analysis: {{ analysis }}
```

### Accessing Nested Data

Use dot notation or dictionary access:

```yaml
prompt: |
  Company size: {{ company.size }}
  First product: {{ company.products[0].name }}
  Revenue: {{ company["financial_data"]["revenue"] }}
```

## Complete Examples

### Example 1: Simple Company Analysis

```yaml
name: Simple Company Analysis
description: Fetches company data and generates an analysis

inputs:
  required: [company_name]
  schema:
    company_name:
      type: string
      description: Company to analyze

nodes:
  fetch_data:
    type: http
    config:
      url: https://api.crunchbase.com/v4/entities/organizations/{{ inputs.company_name }}
      headers:
        X-API-KEY: "{{ env.CRUNCHBASE_API_KEY }}"

  analyze:
    type: llm
    depends_on: [fetch_data]
    config:
      provider: openai
      model: gpt-4
      context:
        data: fetch_data
      prompt: |
        Analyze this company data and provide insights:
        {{ data | tojson(indent=2) }}

outputs:
  mapping:
    analysis: analyze
```

### Example 2: Multi-Source Enrichment

```yaml
name: Multi-Source Company Enrichment
version: 1.0.0

inputs:
  required: [company_name]
  schema:
    company_name:
      type: string
    include_github:
      type: boolean
      default: true

nodes:
  # Classification
  classify:
    type: llm
    config:
      provider: openai
      model: gpt-4
      prompt: |
        Classify this company: {{ inputs.company_name }}
        Return JSON with: industry, size, public (boolean)
      schema:
        industry: string
        size: string
        public: boolean

  # Conditional GitHub search
  check_github:
    type: route
    depends_on: [classify]
    config:
      context:
        classification: classify
      routes:
        - condition: inputs.include_github and classification.industry == "technology"
          output: true
      default: false

  # GitHub search (conditional)
  search_github:
    type: http
    depends_on: [check_github]
    config:
      url: https://api.github.com/search/repositories
      headers:
        Authorization: Bearer {{ env.GITHUB_TOKEN }}
      params:
        q: "org:{{ inputs.company_name }}"
        sort: stars

  # Final analysis
  analyze:
    type: llm
    depends_on: [classify, search_github]
    config:
      provider: anthropic
      model: claude-3-opus-20240229
      context:
        classification: classify
        github_data: search_github
        should_check_github: check_github
      prompt: |
        Company: {{ inputs.company_name }}
        Classification: {{ classification }}

        {% if should_check_github %}
        GitHub repositories found: {{ github_data.total_count }}
        {% endif %}

        Provide a comprehensive analysis.

outputs:
  mapping:
    classification: classify
    github_searched: check_github
    analysis: analyze
```

### Example 3: Document Processing Pipeline

```yaml
name: Document Analysis Pipeline
description: Processes documents and extracts structured information

inputs:
  required: [document_path]
  schema:
    document_path:
      type: string
      description: Path to document file

nodes:
  # Load document
  load_doc:
    type: file
    config:
      path: "{{ inputs.document_path }}"
      format: auto

  # Extract key information
  extract_info:
    type: llm
    depends_on: [load_doc]
    config:
      provider: openai
      model: gpt-4
      context:
        content: load_doc
      prompt: |
        Extract key information from this document:
        {{ content }}
      schema:
        title: string
        summary: string
        key_points:
          type: array
          items: string
        entities:
          people: array
          organizations: array
          locations: array

  # Categorize document
  categorize:
    type: llm
    depends_on: [extract_info]
    config:
      context:
        info: extract_info
      prompt: |
        Based on this information, categorize the document:
        {{ info | tojson(indent=2) }}
      schema:
        category: string
        confidence: number
        tags:
          type: array
          items: string

outputs:
  mapping:
    extracted_info: extract_info
    category: categorize
```

## Best Practices

### 1. Node Design

- **Single Responsibility**: Each node should do one thing well
- **Clear Naming**: Use descriptive node names that indicate their purpose
- **Explicit Dependencies**: Always declare dependencies clearly

### 2. Prompt Engineering

- **Context First**: Provide clear context before the task
- **Structured Output**: Use schemas when you need consistent output format
- **Template Reuse**: Use external templates for complex prompts

### 3. Error Handling

- **Validation**: Use input schemas to validate parameters
- **Defaults**: Provide sensible defaults where appropriate
- **Guard Rails**: Use route nodes to handle edge cases

### 4. Performance

- **Minimize API Calls**: Batch operations where possible
- **Cache Friendly**: Structure workflows to enable future caching
- **Dependency Optimization**: Only depend on nodes you actually need

### 5. Maintainability

- **Version Control**: Use semantic versioning for workflows
- **Documentation**: Document complex logic in descriptions
- **Modularity**: Break complex workflows into smaller, reusable parts

### 6. Security

- **Environment Variables**: Never hardcode sensitive data
- **Input Validation**: Always validate external inputs
- **Output Sanitization**: Be careful with template outputs

## Advanced Patterns

### Parallel Processing (Future)

While not yet implemented, workflows are designed to support parallel execution:

```yaml
# These nodes could run in parallel (no dependencies between them)
fetch_github:
  type: http
  config: ...

fetch_linkedin:
  type: http
  config: ...

fetch_crunchbase:
  type: http
  config: ...

# This node waits for all three
aggregate:
  depends_on: [fetch_github, fetch_linkedin, fetch_crunchbase]
  type: llm
  config: ...
```

### Dynamic Routing

Use route nodes for complex conditional logic:

```yaml
router:
  type: route
  config:
    context:
      doc: document_analysis
    routes:
      - condition: doc.type == "contract" and doc.pages > 50
        output: { pipeline: "complex_contract_analysis" }
      - condition: doc.type == "contract"
        output: { pipeline: "simple_contract_analysis" }
      - condition: doc.type in ["email", "letter"]
        output: { pipeline: "correspondence_analysis" }
    default: { pipeline: "generic_analysis" }
```

### Recursive Patterns (Future)

For future support of recursive/iterative workflows:

```yaml
# Hypothetical syntax for agent nodes (not yet implemented)
research_agent:
  type: agent
  config:
    max_iterations: 5
    tools:
      - search_web
      - read_page
      - summarize
    goal: |
      Research {{ inputs.topic }} and provide a comprehensive report
    success_criteria: |
      Has at least 5 credible sources and covers multiple perspectives
```

## Schema Validation

The workflow schema is defined in `schema/workflow-schema.yaml` and can be used to validate workflow files:

```bash
# Validate a workflow file
s10s validate workflow.yaml

# Test without executing
s10s test workflow.yaml --dry-run
```

This ensures your workflows are correctly structured before execution.
