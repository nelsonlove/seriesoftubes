# Node Type: `route`

Conditionally route workflow execution based on data conditions.

## Properties

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `routes` | array | Conditional routing rules |

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `context` | object | - | Map context variables from other nodes |

## Property Details

### `context`

Map context variables from other nodes

**Type:** `object`

### `routes`

Conditional routing rules

**Type:** `array` | **Required:** Yes


## Examples

### Example 1: Conditional routing

```yaml
route_by_size:
  type: route
  depends_on: [analyze_company]
  config:
    context:
      company: analyze_company
    routes:
      - when: "{{ company.revenue > 1000000 }}"
        to: process_enterprise
      - when: "{{ company.employees < 50 }}"
        to: process_small_business
      - default: true
        to: process_standard
```
