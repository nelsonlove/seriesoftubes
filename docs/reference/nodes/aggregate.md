# Node Type: `aggregate`

Collect parallel results into single output.

## Properties

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `mode` | string | `array` | Aggregation mode: array (collect into array), object (merge into object), merge (deep merge) |
| `field` | string | - | Optional - extract specific field from each result |
| `context` | object | - | Map context variables from other nodes |

## Property Details

### `mode`

Aggregation mode: array (collect into array), object (merge into object), merge (deep merge)

**Type:** `string` | **Default:** `array` | **Allowed values:** `array`, `object`, `merge`

### `field`

Optional - extract specific field from each result

**Type:** `string`

### `context`

Map context variables from other nodes

**Type:** `object`


## Examples
