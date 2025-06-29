# Node Type: `conditional`

Conditionally route or return values based on expressions.

## Properties

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `conditions` | array | List of conditions to evaluate in order |

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `fallback` | string | - | Fallback value if no conditions match and no default |
| `context` | object | - | Map context variables from other nodes |

## Property Details

### `conditions`

List of conditions to evaluate in order

**Type:** `array` | **Required:** Yes

**Array Item Properties:**

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `conditions[].condition` | `string` | No | Jinja2 condition expression (omit for default) |
| `conditions[].then` | `string` | Yes | Target/output value if condition is true |
| `conditions[].is_default` | `boolean` | No | Whether this is the default condition |

### `fallback`

Fallback value if no conditions match and no default

**Type:** `string`

### `context`

Map context variables from other nodes

**Type:** `object`


## Examples

### Example 1: Conditional routing

```yaml
route_by_size:
  type: conditional
  depends_on: [analyze_company]
  config:
    context:
      company: analyze_company
    conditions:
      - condition: "{{ company.revenue > 1000000 }}"
        then: process_enterprise
      - condition: "{{ company.employees < 50 }}"
        then: process_small_business
      - condition: "default"
        then: process_standard
        is_default: true
```
