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
  
  route:
    type: route
    depends_on: [evaluate]
    description: Route based on evaluation
    config:
      condition: "{{ evaluate.is_high }}"
      true_next: high_value_process
      false_next: low_value_process
  
  high_value_process:
    type: llm
    depends_on: [route]
    description: Process high values
    config:
      prompt: |
        The value {{ inputs.value }} exceeds the threshold of {{ inputs.threshold }}.
        Difference: {{ evaluate.difference }}
        
        Provide recommendations for handling this high value.
      model: gpt-3.5-turbo
  
  low_value_process:
    type: llm
    depends_on: [route]
    description: Process low values
    config:
      prompt: |
        The value {{ inputs.value }} is below the threshold of {{ inputs.threshold }}.
        It is at {{ evaluate.percentage }}% of the threshold.
        
        Suggest ways to improve this value.
      model: gpt-3.5-turbo

outputs:
  evaluation: evaluate
  recommendation: route
`,
  },
  {
    name: 'File Processing',
    description: 'Read and process file content',
    yaml: `name: file-processing-example
version: "1.0.0"
description: Read a file and process its content

inputs:
  file_path:
    type: string
    required: true
    description: Path to the file to process

nodes:
  read_file:
    type: file
    description: Read file content
    config:
      operation: read
      path: "{{ inputs.file_path }}"
      encoding: utf-8
  
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
        {{ read_file }}
      model: gpt-4
      temperature: 0.5

outputs:
  content: read_file
  analysis: analyze_content
`,
  },
];