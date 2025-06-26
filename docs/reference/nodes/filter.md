# Node Type: `filter`

Filter arrays based on conditions.

## Properties

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `condition` | string | Jinja2 condition expression |

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `field` | string | - | Array field to filter (if not provided, filters root array) |
| `context` | object | - | Map context variables from other nodes |

## Property Details

### `condition`

Jinja2 condition expression

**Type:** `string` | **Required:** Yes

**Examples:**

- `{{ item.score > 0.8 }}`
- `{{ item.type == 'company' }}`

### `field`

Array field to filter (if not provided, filters root array)

**Type:** `string`

### `context`

Map context variables from other nodes

**Type:** `object`


## Examples
