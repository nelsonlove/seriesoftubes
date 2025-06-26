# Schema Validation Guide

SeriesOfTubes provides automatic runtime schema validation for all node inputs and outputs. This ensures data integrity throughout your workflows and provides clear error messages when validation fails.

## Overview

Every node type in SeriesOfTubes has defined input and output schemas that are automatically validated during execution. This validation happens transparently - you don't need to explicitly enable it or add any configuration.

## Benefits

### 1. Early Error Detection
Schema validation catches data type mismatches and invalid configurations before they cause runtime errors deep in your workflow execution.

### 2. Clear Error Messages
When validation fails, you get specific, actionable error messages that tell you exactly what went wrong and where:

```
Input validation failed for node 'fetch_data':
  - url: Value error, URL cannot be empty
  - headers.Authorization: Value error, Field required
```

### 3. Type Safety
Schemas ensure that data flowing between nodes matches expected types, preventing common errors like passing a string where a number is expected.

### 4. Self-Documenting Workflows
The schemas serve as living documentation for what each node expects and produces, making workflows easier to understand and maintain.

## How It Works

### Input Validation

Before a node executes, its inputs are validated against the defined schema:

1. Template rendering occurs first (Jinja2 expressions are evaluated)
2. The rendered values are validated against the input schema
3. If validation fails, execution stops with a clear error message

Example:
```yaml
# This will fail validation if API_TOKEN env var is not set
api_call:
  type: http
  config:
    url: "{{ env.API_URL }}"  # Will fail if this renders to empty string
    headers:
      Authorization: "Bearer {{ env.API_TOKEN }}"
```

### Output Validation

After a node executes successfully, its output is validated:

1. The node produces its output
2. The output is validated against the output schema
3. If validation fails, the node returns an error result

This ensures downstream nodes receive data in the expected format.

## Node Type Schemas

### LLM Node

**Input Schema:**
- `prompt` (string, required): The prompt to send to the LLM
- `context_data` (dict): Additional context for template rendering

**Output Schema:**
- `response` (string): The LLM's text response
- `structured_output` (dict, optional): Extracted structured data if schema was provided
- `model_used` (string): The model that was used
- `token_usage` (dict, optional): Token usage statistics

### HTTP Node

**Input Schema:**
- `url` (string, required): Must be a valid HTTP/HTTPS URL
- `method` (string): HTTP method (GET, POST, etc.)
- `headers` (dict): HTTP headers
- `params` (dict): Query parameters
- `body` (any): Request body

**Output Schema:**
- `status_code` (int): HTTP response status code
- `headers` (dict): Response headers
- `body` (any): Response body (parsed JSON or text)
- `url` (string): Final URL after redirects

### File Node

**Input Schema:**
- `path` (string, optional): File path to read (cannot be empty if provided)
- `pattern` (string, optional): Glob pattern for multiple files (cannot be empty if provided)

**Output Schema:**
- `data` (any): The loaded file data
- `metadata` (dict): File metadata including:
  - `files_read` (int): Number of files processed
  - `output_mode` (string): How data was returned
  - `format` (string): File format detected/used

### Python Node

**Input Schema:**
- `context` (dict): Context data available to the Python code

**Output Schema:**
- `result` (any): The return value from the Python code (must be JSON-serializable)

## Common Validation Errors

### Empty Required Fields

```yaml
# This will fail - URL is required and cannot be empty
api_call:
  type: http
  config:
    url: ""  # Error: URL cannot be empty
```

### Invalid URL Format

```yaml
# This will fail - URL must start with http:// or https://
api_call:
  type: http
  config:
    url: "ftp://example.com"  # Error: URL must start with http:// or https://
```

### Template Rendering to Invalid Values

```yaml
# This will fail if the environment variable is not set
api_call:
  type: http
  config:
    url: "{{ env.UNDEFINED_VAR }}"  # Renders to empty string, validation fails
```

### Type Mismatches

```yaml
# Python nodes must return JSON-serializable data
calculate:
  type: python
  config:
    code: |
      import datetime
      return datetime.now()  # Error: datetime is not JSON-serializable
```

## Best Practices

### 1. Use Default Values for Optional Inputs

```yaml
inputs:
  api_url:
    type: string
    required: false
    default: "https://api.example.com"  # Prevents empty URL errors
```

### 2. Validate Environment Variables Early

```yaml
# Add a validation node at the start of your workflow
validate_env:
  type: python
  config:
    code: |
      required_vars = ['API_KEY', 'API_URL', 'DATABASE_URL']
      missing = [var for var in required_vars if not context['env'].get(var)]
      if missing:
          raise ValueError(f"Missing required environment variables: {missing}")
      return {"validated": True}
```

### 3. Handle Optional Fields Gracefully

```yaml
# Use Jinja2 default filter for optional values
api_call:
  type: http
  config:
    url: "{{ inputs.api_url | default('https://api.example.com') }}"
    headers:
      Authorization: "Bearer {{ env.API_TOKEN | default('') }}"
```

### 4. Test with Invalid Data

Always test your workflows with invalid or missing data to ensure validation errors are caught and reported clearly:

```bash
# Test with missing environment variable
unset API_TOKEN
s10s run workflow.yaml

# Test with invalid input
s10s run workflow.yaml --inputs url="not-a-url"
```

## Debugging Validation Errors

When you encounter a validation error:

1. **Check the error message** - It will tell you exactly which field failed and why
2. **Verify template rendering** - Use debug nodes to see what values templates produce
3. **Check environment variables** - Ensure all referenced env vars are set
4. **Validate input types** - Ensure inputs match the expected types

Example debug node:
```yaml
debug_context:
  type: python
  config:
    code: |
      print("URL will be:", context['inputs'].get('api_url', 'NOT SET'))
      print("Token exists:", bool(context['env'].get('API_TOKEN')))
      return {"debug": "complete"}
```

## Future Enhancements

The schema validation system will be enhanced with:

- Custom validation rules per workflow
- Schema versioning and migration tools
- Visual schema documentation in the UI
- IDE autocomplete based on schemas
- Runtime type checking for complex nested structures

By leveraging SeriesOfTubes' automatic schema validation, you can build more robust workflows that fail fast with clear errors rather than producing incorrect results silently.