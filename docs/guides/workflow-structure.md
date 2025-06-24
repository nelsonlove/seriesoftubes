# Workflow Structure Guide

This guide explains the structure of SeriesOfTubes workflow files.

## Basic Structure

Every workflow is a YAML file with the following top-level properties:

```yaml
name: My Workflow Name
version: "1.0.0"
description: What this workflow does

inputs:
  # Define input parameters

nodes:
  # Define workflow nodes (DAG)

outputs:
  # Define what to return
```

## Workflow Properties

### `name`

Human-readable name for the workflow

**Type:** `string`
**Required:** Yes

### `version`

Semantic version of the workflow

**Type:** `string`
**Required:** No
**Default:** `1.0.0`
**Pattern:** `^\d+\.\d+\.\d+$`

### `description`

Detailed description of what the workflow does

**Type:** `string`
**Required:** No

### `inputs`

Input parameters for the workflow

**Type:** `object`
**Required:** No

### `nodes`

DAG nodes that make up the workflow

**Type:** `object`
**Required:** Yes

### `outputs`

Map output names to node names

**Type:** `object`
**Required:** No

## Input Types

Workflow inputs support the following types:

- `string` - Text values
- `number` - Numeric values (float)
- `integer` - Whole numbers
- `boolean` - True/false values
- `object` - JSON objects
- `array` - Lists of values

### Input Definition Examples

```yaml
inputs:
  # Simple string input (shorthand)
  company_name: string
  
  # Detailed input with constraints
  threshold:
    type: number
    required: false
    default: 100
    description: Revenue threshold
  
  # Object input
  config:
    type: object
    required: true
```

## Node Dependencies

Nodes can depend on other nodes, creating a directed acyclic graph (DAG):

```yaml
nodes:
  fetch_data:
    type: http
    config:
      url: https://api.example.com/data
  
  process_data:
    type: python
    depends_on: [fetch_data]  # Waits for fetch_data to complete
    config:
      context:
        data: fetch_data  # Access output from fetch_data
```

## Context Mapping

Nodes can access data from:

- Previous node outputs via context mapping
- Workflow inputs via `inputs` in context
- Environment variables via Jinja2 templates

```yaml
process:
  type: python
  depends_on: [fetch_data, classify]
  config:
    context:
      raw_data: fetch_data
      classification: classify
    code: |
      # Access context variables
      data = context['raw_data']
      category = context['classification']
      threshold = context['inputs']['threshold']
```
