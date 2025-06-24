# Node Type: `http`

Make HTTP API calls with authentication and templating support.

## Properties

### Required Properties

| Property | Type | Description |
|----------|------|-------------|
| `url` | string | HTTP endpoint URL (supports Jinja2 templates) |

### Optional Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `method` | string | `GET` | HTTP method |
| `headers` | object | - | HTTP headers (supports Jinja2 templates) |
| `body` | any | - | Request body (supports Jinja2 templates) |
| `auth` | object | - | Authentication configuration |
| `context` | object | - | Map context variables from other nodes |

## Property Details

### `url`

HTTP endpoint URL (supports Jinja2 templates)

**Type:** `string` | **Required:** Yes | **Format:** uri

### `method`

HTTP method

**Type:** `string` | **Default:** `GET` | **Allowed values:** `GET`, `POST`, `PUT`, `DELETE`, `PATCH`

### `headers`

HTTP headers (supports Jinja2 templates)

**Type:** `object`

### `body`

Request body (supports Jinja2 templates)

**Type:** `any`

### `auth`

Authentication configuration

**Type:** `object`

### `context`

Map context variables from other nodes

**Type:** `object`


## Examples

### Example 1: Simple GET request

```yaml
fetch_api:
  type: http
  config:
    url: https://api.example.com/data
    method: GET
```

### Example 2: POST with authentication

```yaml
create_record:
  type: http
  depends_on: [prepare_data]
  config:
    url: https://api.example.com/records
    method: POST
    headers:
      Content-Type: application/json
    auth:
      type: bearer
      token: "{{ env.API_TOKEN }}"
    body: "{{ prepare_data }}"
    context:
      prepare_data: prepare_data
```
