export interface WorkflowInput {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  required?: boolean;
  default?: any;
  description?: string;
}

export interface WorkflowNode {
  type:
    | 'llm'
    | 'http'
    | 'route'
    | 'file'
    | 'python'
    | 'split'
    | 'aggregate'
    | 'filter'
    | 'transform'
    | 'join'
    | 'foreach'
    | 'conditional';
  depends_on?: string[];
  config: Record<string, any>;
  description?: string;
}

export interface Workflow {
  name: string;
  version: string;
  description?: string;
  inputs: Record<string, WorkflowInput>;
  nodes: Record<string, WorkflowNode>;
  outputs: Record<string, string>;
}

export interface WorkflowSummary {
  id: string;
  name: string;
  version: string;
  description?: string;
  user_id: string;
  username: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
  yaml_content: string;
  // Computed fields for UI
  path: string;
  inputs: Record<string, WorkflowInput>;
}

export interface WorkflowResponse {
  id: string;
  name: string;
  version: string;
  description?: string;
  user_id: string;
  username: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
  yaml_content: string;
}

export interface WorkflowDetail {
  id: string;
  name: string;
  version: string;
  description?: string;
  user_id: string;
  username: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
  yaml_content: string;
  parsed?: Workflow;
  // For backwards compatibility
  path?: string;
  workflow?: Workflow;
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
  error_details?: Record<string, {
    error: string;
    inputs: Record<string, any>;
    timestamp: string;
  }>;
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
