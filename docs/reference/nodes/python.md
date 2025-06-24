# Node Type: `python`

Execute Python code for data transformation and analysis.

## Properties

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `code` | string | - | Inline Python code to execute |
| `file` | string | - | Path to Python file (supports Jinja2 templates) |
| `function` | string | - | Function name to call if using file |
| `context` | object | - | Map context variables from other nodes |
| `timeout` | integer | `30` | Execution timeout in seconds |
| `memory_limit` | string | `100MB` | Memory limit (e.g., '100MB', '1GB') |
| `allowed_imports` | array | `[]` | List of allowed module imports |
| `max_output_size` | integer | `10485760` | Maximum output size in bytes (10MB default) |

### Property Constraints

You must provide ONE of the following property combinations:

1. `code`
2. `file`

## Property Details

### `code`

Inline Python code to execute

**Type:** `string`

### `file`

Path to Python file (supports Jinja2 templates)

**Type:** `string`

### `function`

Function name to call if using file

**Type:** `string`

### `context`

Map context variables from other nodes

**Type:** `object`

### `timeout`

Execution timeout in seconds

**Type:** `integer` | **Default:** `30` | **Minimum:** 1 | **Maximum:** 300

### `memory_limit`

Memory limit (e.g., '100MB', '1GB')

**Type:** `string` | **Default:** `100MB` | **Pattern:** `^\d+(\.\d+)?(KB|MB|GB)?$`

### `allowed_imports`

List of allowed module imports

**Type:** `array` | **Default:** `[]`

**Examples:**

- `['math', 'statistics', 'collections']`
- `['pandas', 'numpy']`

### `max_output_size`

Maximum output size in bytes (10MB default)

**Type:** `integer` | **Default:** `10485760` | **Minimum:** 1024 | **Maximum:** 104857600


## Examples

### Example 1: Data transformation

```yaml
transform_data:
  type: python
  depends_on: [load_data]
  config:
    code: |
      data = context['data']
      
      # Transform and filter
      result = {
          'total': len(data),
          'filtered': [d for d in data if d.get('active')],
          'summary': {
              'avg_revenue': sum(d.get('revenue', 0) for d in data) / len(data)
          }
      }
      
      return result
    context:
      data: load_data
```
