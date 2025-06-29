export interface WorkflowTemplate {
  name: string;
  description: string;
  yaml: string;
}

export const workflowTemplates: WorkflowTemplate[] = [
  {
    name: 'Simple LLM Workflow',
    description: 'Basic workflow that processes text with an LLM',
    yaml: `name: simple-llm-example
version: "1.0.0"
description: A simple workflow that processes text with an LLM

inputs:
  text:
    type: string
    required: true
    description: The text to process

nodes:
  process:
    type: llm
    description: Process the input text
    config:
      prompt: |
        Please analyze the following text and provide a summary:

        {{ inputs.text }}
      model: gpt-4
      temperature: 0.7
      max_tokens: 500

outputs:
  result: process
`,
  },
  {
    name: 'HTTP API Integration',
    description: 'Workflow that calls an external API and processes the response',
    yaml: `name: api-integration-example
version: "1.0.0"
description: Fetch data from an API and analyze it

inputs:
  query:
    type: string
    required: true
    description: Search query for the API

nodes:
  fetch_data:
    type: http
    description: Fetch data from external API
    config:
      url: "https://api.example.com/search"
      method: GET
      params:
        q: "{{ inputs.query }}"
      headers:
        Accept: "application/json"

  analyze:
    type: llm
    depends_on: [fetch_data]
    description: Analyze the API response
    config:
      prompt: |
        Analyze this API response and extract key information:

        {{ fetch_data }}
      model: gpt-4
      temperature: 0.3

outputs:
  api_data: fetch_data
  analysis: analyze
`,
  },
  {
    name: 'Python Processing',
    description: 'Workflow using Python code for data processing',
    yaml: `name: python-processing-example
version: "1.0.0"
description: Process data using Python code

inputs:
  numbers:
    type: array
    required: true
    description: List of numbers to process

nodes:
  calculate:
    type: python
    description: Calculate statistics
    config:
      code: |
        import statistics

        numbers = context['numbers']

        return {
          'count': len(numbers),
          'sum': sum(numbers),
          'mean': statistics.mean(numbers) if numbers else 0,
          'median': statistics.median(numbers) if numbers else 0,
          'min': min(numbers) if numbers else None,
          'max': max(numbers) if numbers else None
        }
      context:
        numbers: inputs.numbers

outputs:
  statistics: calculate
`,
  },
  {
    name: 'Conditional Routing',
    description: 'Workflow with conditional logic and routing',
    yaml: `name: conditional-routing-example
version: "1.0.0"
description: Route processing based on conditions

inputs:
  value:
    type: number
    required: true
    description: Value to evaluate
  threshold:
    type: number
    required: false
    default: 100
    description: Threshold for routing decision

nodes:
  evaluate:
    type: python
    description: Evaluate the input value
    config:
      code: |
        value = context['value']
        threshold = context['threshold']

        return {
          'is_high': value > threshold,
          'difference': value - threshold,
          'percentage': (value / threshold * 100) if threshold != 0 else 0
        }
      context:
        value: inputs.value
        threshold: inputs.threshold

  route_decision:
    type: conditional
    depends_on: [evaluate]
    description: Route based on evaluation
    config:
      condition: "{{ evaluate.is_high }}"
      outputs:
        true: high_value_process
        false: low_value_process

  high_value_process:
    type: llm
    depends_on: [route_decision]
    description: Process high values
    config:
      prompt: |
        The value {{ inputs.value }} exceeds the threshold of {{ inputs.threshold }}.
        Difference: {{ evaluate.difference }}

        Provide recommendations for handling this high value.
      model: gpt-3.5-turbo

  low_value_process:
    type: llm
    depends_on: [route_decision]
    description: Process low values
    config:
      prompt: |
        The value {{ inputs.value }} is below the threshold of {{ inputs.threshold }}.
        It is at {{ evaluate.percentage }}% of the threshold.

        Suggest ways to improve this value.
      model: gpt-3.5-turbo

outputs:
  evaluation: evaluate
  recommendation: route_decision
`,
  },
  {
    name: 'File Processing',
    description: 'Read and process uploaded file content',
    yaml: `name: file-processing-example
version: "1.0.0"
description: Read and analyze an uploaded file

inputs:
  input_file:
    type: string
    input_type: file
    required: true
    description: Select a file to analyze

nodes:
  read_file:
    type: file
    description: Read file content
    config:
      path: "{{ inputs.input_file }}"
      storage_type: object
      format_type: auto

  analyze_content:
    type: llm
    depends_on: [read_file]
    description: Analyze file content
    config:
      prompt: |
        Analyze the following file content and provide:
        1. A summary of the content
        2. Key topics or themes
        3. Any notable patterns or insights

        File content:
        {{ read_file.data }}
      model: gpt-4
      temperature: 0.5

  save_analysis:
    type: file
    depends_on: [analyze_content]
    description: Save analysis results
    config:
      mode: write
      write_key: "outputs/analysis_{{ execution_id }}.json"
      storage_type: object
      format_type: json

outputs:
  original_content: read_file.data
  analysis: analyze_content
  saved_file: save_analysis.key
`,
  },
  {
    name: 'Data Processing Pipeline',
    description: 'Process CSV data and generate insights',
    yaml: `name: data-processing-pipeline
version: "1.0.0"
description: Process CSV data, analyze it, and save results

inputs:
  data_file:
    type: string
    input_type: file
    required: true
    description: Select a CSV file with data to process

nodes:
  load_data:
    type: file
    description: Load CSV data
    config:
      path: "{{ inputs.data_file }}"
      storage_type: object
      format_type: csv

  process_data:
    type: python
    depends_on: [load_data]
    description: Process and analyze the data
    config:
      code: |
        import pandas as pd
        import json
        
        # Data is already loaded as a list of dicts from CSV
        data = context['data']
        df = pd.DataFrame(data)
        
        # Basic statistics
        stats = {
          'row_count': len(df),
          'columns': list(df.columns),
          'numeric_columns': list(df.select_dtypes(include=['int64', 'float64']).columns),
          'summary': {}
        }
        
        # Generate summary statistics for numeric columns
        for col in stats['numeric_columns']:
          stats['summary'][col] = {
            'mean': float(df[col].mean()),
            'median': float(df[col].median()),
            'min': float(df[col].min()),
            'max': float(df[col].max()),
            'std': float(df[col].std())
          }
        
        return stats
      context:
        data: load_data.data

  generate_report:
    type: llm
    depends_on: [process_data]
    description: Generate insights report
    config:
      prompt: |
        Based on the following data analysis, generate a comprehensive report:
        
        {{ process_data }}
        
        Please provide:
        1. Executive summary of the data
        2. Key findings from the statistics
        3. Potential insights or patterns
        4. Recommendations for further analysis
      model: gpt-4
      temperature: 0.7

  save_results:
    type: file
    depends_on: [process_data, generate_report]
    description: Save processing results
    config:
      mode: write
      write_key: "outputs/data_analysis_{{ execution_id }}.json"
      storage_type: object
      format_type: json

outputs:
  statistics: process_data
  report: generate_report
  output_file: save_results.key
`,
  },
];
