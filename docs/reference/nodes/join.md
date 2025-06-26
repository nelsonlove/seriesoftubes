# Node Type: `join`

Join multiple data sources using various join strategies.

## Properties

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `sources` | object | Named data sources to join (name -> node.field) |

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `join_type` | string | `merge` | Type of join to perform |
| `join_keys` | object | - | Join key mappings for inner/left joins (source1_key -> source2_key) |
| `context` | object | - | Map context variables from other nodes |

## Property Details

### `sources`

Named data sources to join (name -> node.field)

**Type:** `object` | **Required:** Yes

**Examples:**

```yaml
left: companies_data
right: revenue_data.companies
```

### `join_type`

Type of join to perform

**Type:** `string` | **Default:** `merge` | **Allowed values:** `inner`, `left`, `right`, `outer`, `cross`, `merge`

### `join_keys`

Join key mappings for inner/left joins (source1_key -> source2_key)

**Type:** `object`

**Examples:**

```yaml
company_id: id
name: company_name
```

### `context`

Map context variables from other nodes

**Type:** `object`


## Examples
