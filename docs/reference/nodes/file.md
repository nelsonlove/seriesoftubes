# Node Type: `file`

Read and process files in various formats (JSON, CSV, YAML, PDF, etc.).

## Properties

### Optional Properties

| Property       | Type    | Default   | Description                                                       |
|----------------|---------|-----------|-------------------------------------------------------------------|
| `path`         | string  | -         | Single file path (supports Jinja2 templates)                      |
| `pattern`      | string  | -         | Glob pattern for multiple files                                   |
| `context`      | object  | -         | Map context variables from other nodes                            |
| `format`       | string  | `auto`    | File format (auto-detected by default)                            |
| `encoding`     | string  | `utf-8`   | Text encoding for text files                                      |
| `extract_text` | boolean | `True`    | Extract text from documents (PDF, DOCX, HTML)                     |
| `output_mode`  | string  | `content` | Output mode - content (single), list (records), dict (collection) |
| `merge`        | boolean | `False`   | Merge multiple files into single output                           |
| `stream`       | boolean | `False`   | Stream large files in chunks                                      |
| `chunk_size`   | integer | `1000`    | Rows per chunk for streaming                                      |
| `sample`       | number  | -         | Sample fraction (0.0-1.0)                                         |
| `limit`        | integer | -         | Limit number of records                                           |
| `delimiter`    | string  | `,`       | CSV delimiter                                                     |
| `has_header`   | boolean | `True`    | CSV has header row                                                |
| `skip_errors`  | boolean | `False`   | Skip files/rows with errors                                       |

### Property Constraints

You must provide ONE of the following property combinations:

1. `path`
2. `pattern`

## Property Details

### `path`

Single file path (supports Jinja2 templates)

**Type:** `string`

### `pattern`

Glob pattern for multiple files

**Type:** `string`

### `context`

Map context variables from other nodes

**Type:** `object`

### `format`

File format (auto-detected by default)

**Type:** `string` | **Default:** `auto` | **Allowed values:** `auto`, `json`, `jsonl`, `csv`, `yaml`, `txt`, `pdf`,
`docx`, `xlsx`, `html`

### `encoding`

Text encoding for text files

**Type:** `string` | **Default:** `utf-8`

### `extract_text`

Extract text from documents (PDF, DOCX, HTML)

**Type:** `boolean` | **Default:** `True`

### `output_mode`

Output mode - content (single), list (records), dict (collection)

**Type:** `string` | **Default:** `content` | **Allowed values:** `content`, `list`, `dict`

### `merge`

Merge multiple files into single output

**Type:** `boolean` | **Default:** `False`

### `stream`

Stream large files in chunks

**Type:** `boolean` | **Default:** `False`

### `chunk_size`

Rows per chunk for streaming

**Type:** `integer` | **Default:** `1000`

### `sample`

Sample fraction (0.0-1.0)

**Type:** `number` | **Minimum:** 0.0 | **Maximum:** 1.0

### `limit`

Limit number of records

**Type:** `integer` | **Minimum:** 1

### `delimiter`

CSV delimiter

**Type:** `string` | **Default:** `,`

### `has_header`

CSV has header row

**Type:** `boolean` | **Default:** `True`

### `skip_errors`

Skip files/rows with errors

**Type:** `boolean` | **Default:** `False`

## Examples

### Example 1: Read JSON file

```yaml
load_data:
  type: file
  config:
    path: data/companies.json
    format: json
```

### Example 2: Process CSV files

```yaml
load_csv_data:
  type: file
  config:
    pattern: data/*.csv
    format: csv
    merge: true
    skip_errors: true
```
