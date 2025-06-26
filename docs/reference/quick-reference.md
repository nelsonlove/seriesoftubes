# SeriesOfTubes Quick Reference

## Available Node Types

| Node Type | Purpose | Key Properties |
|-----------|---------|----------------|
| `llm` | LLM API calls | `prompt`, `model`, `schema` |
| `http` | HTTP requests | `url`, `method`, `headers` |
| `file` | File operations | `path`/`pattern`, `format` |
| `python` | Python execution | `code`/`file`, `context` |
| `split` | Split arrays | `field`, `item_name` |
| `aggregate` | Collect results | `mode`, `field` |
| `filter` | Filter arrays | `condition`, `field` |
| `transform` | Transform data | `template`, `field` |
| `join` | Join data sources | `sources`, `join_type` |
| `foreach` | Iterate subgraph | `array_field`, `subgraph_nodes` |
| `conditional` | Conditional logic | `conditions`, `fallback` |

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

### Conditional Logic
```yaml
decide_action:
  type: conditional
  config:
    conditions:
      - condition: "{{ score > 0.8 }}"
        then: process_high_value
      - condition: "{{ score > 0.5 }}"
        then: process_medium
      - is_default: true
        then: process_low
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
