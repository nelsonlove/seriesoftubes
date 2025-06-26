# Node Type: `foreach`

Execute a subgraph for each item in an array.

## Properties

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `array_field` | string | Field containing array to iterate over |
| `subgraph_nodes` | array | List of node names to execute for each item |

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `item_name` | string | `item` | Name for each item in subgraph context |
| `parallel` | boolean | `True` | Execute iterations in parallel (default) or sequentially |
| `collect_output` | string | - | Output field name to collect from each iteration |
| `context` | object | - | Map context variables from other nodes |

## Property Details

### `array_field`

Field containing array to iterate over

**Type:** `string` | **Required:** Yes

### `item_name`

Name for each item in subgraph context

**Type:** `string` | **Default:** `item`

### `subgraph_nodes`

List of node names to execute for each item

**Type:** `array` | **Required:** Yes

### `parallel`

Execute iterations in parallel (default) or sequentially

**Type:** `boolean` | **Default:** `True`

### `collect_output`

Output field name to collect from each iteration

**Type:** `string`

### `context`

Map context variables from other nodes

**Type:** `object`


## Examples
