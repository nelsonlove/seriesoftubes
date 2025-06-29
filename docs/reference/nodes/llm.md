# Node Type: `llm`

Execute Large Language Model (LLM) API calls with optional structured extraction.

## Properties

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `provider` | string | `openai` | LLM provider to use |
| `model` | string | - | Model identifier |
| `prompt` | string | - | Inline prompt template (Jinja2) |
| `prompt_template` | string | - | Path to external prompt template file |
| `context` | object | - | Map context variables from other nodes |
| `schema` | object | - | JSON schema for structured extraction |
| `temperature` | number | `0.7` | LLM temperature setting |
| `max_tokens` | integer | - | Maximum tokens in response |

### Property Constraints

You must provide ONE of the following property combinations:

1. `prompt`
2. `prompt_template`

## Property Details

### `provider`

LLM provider to use

**Type:** `string` | **Default:** `openai` | **Allowed values:** `openai`, `anthropic`

### `model`

Model identifier

**Type:** `string`

**Examples:**

- `gpt-4o`
- `claude-3-opus-20240229`

### `prompt`

Inline prompt template (Jinja2)

**Type:** `string`

### `prompt_template`

Path to external prompt template file

**Type:** `string`

### `context`

Map context variables from other nodes

**Type:** `object`

**Examples:**

```yaml
data: fetch_data
classification: classify_company
```

### `schema`

JSON schema for structured extraction

**Type:** `object`

### `temperature`

LLM temperature setting

**Type:** `number` | **Default:** `0.7` | **Minimum:** 0 | **Maximum:** 2

### `max_tokens`

Maximum tokens in response

**Type:** `integer` | **Minimum:** 1


## Examples

### Example 1: Basic prompt

```yaml
classify_company:
  type: llm
  config:
    prompt: "Classify this company: {{ company_name }}"
    model: gpt-4
    temperature: 0.7
```

### Example 2: Structured extraction

```yaml
extract_data:
  type: llm
  depends_on: [fetch_data]
  config:
    prompt_template: prompts/extract.j2
    model: gpt-4
    context:
      data: fetch_data
    schema:
      type: object
      properties:
        revenue:
          type: number
        employees:
          type: integer
        industry:
          type: string
```
