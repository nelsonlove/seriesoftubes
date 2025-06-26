# Node Type: `split`

Split arrays into parallel processing streams.

## Properties

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `field` | string | Field containing array to split |

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `item_name` | string | `item` | Name for each item in downstream context |
| `context` | object | - | Map context variables from other nodes |

## Property Details

### `field`

Field containing array to split

**Type:** `string` | **Required:** Yes

### `item_name`

Name for each item in downstream context

**Type:** `string` | **Default:** `item`

### `context`

Map context variables from other nodes

**Type:** `object`


## Examples
