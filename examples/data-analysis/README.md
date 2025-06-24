# Data Analysis Pipeline Example

This example demonstrates the powerful capabilities of SeriesOfTubes Python nodes for data analysis workflows.

## Overview

The workflow performs a complete data analysis pipeline:

1. **Data Loading**: Reads company data from a JSON file
2. **Data Processing**: Filters and analyzes companies using Python
3. **Insight Generation**: Calculates statistics and generates business insights
4. **Export**: Formats results in different output formats

## Features Demonstrated

### Python Node Capabilities
- **Complex Data Processing**: List comprehensions, dictionaries, loops
- **Mathematical Calculations**: Statistics, variance, standard deviation
- **Module Imports**: Safe use of `math` and `json` modules
- **Context Access**: Data flow between nodes
- **Return Values**: Structured output with nested objects

### Security Features
- **Restricted Execution**: Only allowed builtins are available
- **Import Control**: Explicit allowlist for module imports
- **Resource Limits**: Timeout and memory constraints
- **Safe Environment**: Sandboxed execution in separate process

## Running the Workflow

### Basic execution:
```bash
s10s run examples/data-analysis/workflow.yaml
```

### With custom threshold:
```bash
s10s run examples/data-analysis/workflow.yaml --inputs threshold=1000000
```

### With summary format:
```bash
s10s run examples/data-analysis/workflow.yaml --inputs export_format=summary
```

## Expected Output

The workflow generates:

- **Filtered Companies**: Companies above the revenue threshold
- **Industry Breakdown**: Companies grouped by industry
- **Statistics**: Revenue and employee metrics per industry
- **Insights**: Automated business insights including:
  - Top performing industry
  - Industry diversity analysis
  - Revenue distribution analysis

## Sample Results

With default threshold (100,000):
- Filters companies with revenue > $100K
- Identifies top industries (Technology, Healthcare, Finance)
- Calculates diversity scores and revenue distribution
- Exports in JSON or summary format

## Advanced Usage

### Testing the Workflow
```bash
s10s test examples/data-analysis/workflow.yaml --dry-run
```

### Validating the Schema
```bash
s10s validate examples/data-analysis/workflow.yaml
```

## Python Node Best Practices

This example demonstrates several best practices:

1. **Explicit Context Mapping**: Clear variable names in context
2. **Error Handling**: Defensive programming with `.get()` methods
3. **Structured Returns**: Well-organized output dictionaries
4. **Import Safety**: Only importing necessary modules
5. **Data Validation**: Checking for empty lists and division by zero
6. **Documentation**: Clear comments explaining the logic

## Extending the Example

You can extend this workflow by:

- Adding more data sources (CSV, API calls)
- Implementing additional statistical analyses
- Creating visualizations (with allowed plotting libraries)
- Adding data validation and cleaning steps
- Implementing machine learning predictions
- Exporting to different formats (CSV, Excel, PDF)

## Security Considerations

The Python nodes in this example are configured with:
- Restricted builtins (no `exec`, `eval`, `open`, etc.)
- Limited imports (`math` and `json` only)
- 30-second execution timeout
- 100MB memory limit
- 10MB output size limit

These settings ensure safe execution while providing powerful data processing capabilities.
