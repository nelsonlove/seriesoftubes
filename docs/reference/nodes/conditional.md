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
