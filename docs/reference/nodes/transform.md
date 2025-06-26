# Node Type: `transform`

Transform data structures using templates.

## Properties

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `template` | string | object | Jinja2 template for transforming each item |

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `field` | string | - | Array field to transform (if not provided, transforms root array) |
| `context` | object | - | Map context variables from other nodes |

## Property Details

### `template`

Jinja2 template for transforming each item

**Type:** `string | object` | **Required:** Yes

**Examples:**

- `{{ item | upper }}`
```yaml
name: {{ item.name }}
score: {{ item.score * 100 }}
```

### `field`

Array field to transform (if not provided, transforms root array)

**Type:** `string`

### `context`

Map context variables from other nodes

**Type:** `object`


## Examples
