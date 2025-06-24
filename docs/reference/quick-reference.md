# SeriesOfTubes Quick Reference

## Available Node Types

| Node Type | Purpose             | Key Properties              |
|-----------|---------------------|-----------------------------|
| `llm`     | LLM API calls       | `prompt`, `model`, `schema` |
| `http`    | HTTP requests       | `url`, `method`, `headers`  |
| `route`   | Conditional routing | `routes`, `when`, `to`      |
| `file`    | File operations     | `path`/`pattern`, `format`  |
| `python`  | Python execution    | `code`/`file`, `context`    |

## Common Patterns

### LLM with Structured Output

```yaml
extract_info:
  type: llm
  config:
    prompt: "Extract company info from: {{ text }}"
    model: gpt-4
    schema:
      type: object
      properties:
        name: { type: string }
        revenue: { type: number }
```

### API Call with Auth

```yaml
api_call:
  type: http
  config:
    url: https://api.example.com/data
    auth:
      type: bearer
      token: "{{ env.API_TOKEN }}"
```

### Conditional Routing

```yaml
route:
  type: route
  config:
    routes:
      - when: "{{ value > 100 }}"
        to: high_value_path
      - default: true
        to: standard_path
```

### Python Data Processing

```yaml
analyze:
  type: python
  config:
    code: |
      data = context['data']
      return {
          'count': len(data),
          'sum': sum(d['value'] for d in data)
      }
```

## Jinja2 Template Variables

- `{{ node_name }}` - Output from another node
- `{{ inputs.param_name }}` - Workflow input parameter
- `{{ env.VAR_NAME }}` - Environment variable
- `{{ item }}` - Current item in loops

## Tips

1. Use `depends_on` to control execution order
2. Map node outputs with `context` in config
3. Use `prompt_template` for complex prompts
4. Enable `skip_errors: true` for fault tolerance
5. Use `schema` in LLM nodes for structured data
