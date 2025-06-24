export interface WorkflowInput {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  required?: boolean;
  default?: any;
  description?: string;
}

export interface WorkflowNode {
  type: 'llm' | 'http' | 'route' | 'file' | 'python';
  depends_on?: string[];
  config: Record<string, any>;
}

export interface Workflow {
  inputs: Record<string, WorkflowInput>;
  nodes: Record<string, WorkflowNode>;
  outputs: Record<string, string>;
}

export interface WorkflowSummary {
  path: string;
  name: string;
  version: string;
  description?: string;
  inputs: Record<string, WorkflowInput>;
}

export interface WorkflowDetail {
  path: string;
  workflow: Workflow;
}

export interface ExecutionInput {
  [key: string]: any;
}

export interface ExecutionResponse {
  id?: string;
  execution_id?: string;
  status: string;
  workflow_path?: string;
  workflow_name: string;
  created_at?: string;
  start_time?: string;
  completed_at?: string;
  end_time?: string;
  outputs?: Record<string, any>;
  errors?: Record<string, string>;
  error?: string;
  progress?: Record<string, string | ExecutionProgress>;
}

export interface ExecutionProgress {
  node: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at?: string;
  completed_at?: string;
  error?: string;
  output?: any;
}

export interface ExecutionDetail extends ExecutionResponse {
  inputs?: ExecutionInput;
  outputs?: Record<string, any>;
  progress?: Record<string, string | ExecutionProgress>;
}
