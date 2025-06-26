// MSW request handlers
import { http, HttpResponse } from 'msw';
import type { WorkflowSummary, WorkflowDetail, Execution } from '../../types/workflow';

const baseUrl = 'http://localhost:8000';

// Mock data
export const mockWorkflows: WorkflowSummary[] = [
  {
    id: '1',
    name: 'Test Workflow 1',
    description: 'A test workflow for unit testing',
    path: '/workflows/test-workflow-1.yaml',
    version: '1.0.0',
    inputs: {
      company: { type: 'string', required: true },
      location: { type: 'string', required: false, default: 'USA' },
    },
    is_public: true,
    username: 'testuser',
    created_at: '2025-06-26T10:00:00Z',
    updated_at: '2025-06-26T10:00:00Z',
  },
  {
    id: '2',
    name: 'Test Workflow 2',
    description: 'Another test workflow',
    path: '/workflows/test-workflow-2.yaml',
    version: '1.0.0',
    inputs: {
      data: { type: 'array', required: true },
    },
    is_public: false,
    username: 'testuser',
    created_at: '2025-06-26T11:00:00Z',
    updated_at: '2025-06-26T11:00:00Z',
  },
];

export const mockWorkflowDetail: WorkflowDetail = {
  id: '1',
  name: 'Test Workflow 1',
  description: 'A test workflow for unit testing',
  path: '/workflows/test-workflow-1.yaml',
  version: '1.0.0',
  inputs: {
    company: { type: 'string', required: true },
    location: { type: 'string', required: false, default: 'USA' },
  },
  nodes: {
    fetch_data: {
      type: 'http',
      config: {
        url: 'https://api.example.com/companies/{{ inputs.company }}',
        method: 'GET',
      },
    },
    analyze: {
      type: 'llm',
      depends_on: ['fetch_data'],
      config: {
        prompt: 'Analyze this company data: {{ fetch_data }}',
        model: 'gpt-4',
      },
    },
  },
  outputs: {
    result: 'analyze',
  },
  is_public: true,
  username: 'testuser',
  created_at: '2025-06-26T10:00:00Z',
  updated_at: '2025-06-26T10:00:00Z',
  content: `name: Test Workflow 1
version: "1.0.0"
description: A test workflow for unit testing

inputs:
  company:
    type: string
    required: true
  location:
    type: string
    required: false
    default: "USA"

nodes:
  fetch_data:
    type: http
    config:
      url: "https://api.example.com/companies/{{ inputs.company }}"
      method: GET

  analyze:
    type: llm
    depends_on: [fetch_data]
    config:
      prompt: |
        Analyze this company data: {{ fetch_data }}
      model: "gpt-4"

outputs:
  result: analyze`,
};

export const mockExecution: Execution = {
  id: 'exec-1',
  workflow_id: '1',
  workflow_name: 'Test Workflow 1',
  status: 'completed',
  inputs: { company: 'Acme Corp', location: 'Boston' },
  outputs: { result: { analysis: 'Company is doing well' } },
  created_at: '2025-06-26T12:00:00Z',
  completed_at: '2025-06-26T12:01:00Z',
  error: null,
  node_executions: [
    {
      node_name: 'fetch_data',
      status: 'completed',
      started_at: '2025-06-26T12:00:00Z',
      completed_at: '2025-06-26T12:00:30Z',
      output: { revenue: '$10M', employees: 50 },
      error: null,
    },
    {
      node_name: 'analyze',
      status: 'completed',
      started_at: '2025-06-26T12:00:30Z',
      completed_at: '2025-06-26T12:01:00Z',
      output: { analysis: 'Company is doing well' },
      error: null,
    },
  ],
};

// Request handlers
export const handlers = [
  // Auth endpoints
  http.post(`${baseUrl}/auth/login`, () => {
    return HttpResponse.json({
      access_token: 'test-token',
      token_type: 'bearer',
    });
  }),

  http.post(`${baseUrl}/auth/register`, () => {
    return HttpResponse.json({
      username: 'testuser',
      email: 'test@example.com',
      id: '1',
    });
  }),

  http.get(`${baseUrl}/auth/me`, ({ request }) => {
    const token = request.headers.get('Authorization');
    if (!token || token !== 'Bearer test-token') {
      return new HttpResponse(null, { status: 401 });
    }
    return HttpResponse.json({
      username: 'testuser',
      email: 'test@example.com',
      id: '1',
    });
  }),

  // Workflow endpoints
  http.get(`${baseUrl}/api/workflows`, () => {
    return HttpResponse.json(mockWorkflows);
  }),

  http.get(`${baseUrl}/api/workflows/:id`, ({ params }) => {
    const { id } = params;
    if (id === '1') {
      return HttpResponse.json(mockWorkflowDetail);
    }
    return new HttpResponse(null, { status: 404 });
  }),

  http.post(`${baseUrl}/api/workflows`, () => {
    return HttpResponse.json({
      ...mockWorkflows[0],
      id: '3',
      name: 'New Workflow',
    });
  }),

  http.delete(`${baseUrl}/api/workflows/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.post(`${baseUrl}/api/workflows/:id/execute`, () => {
    return HttpResponse.json({
      execution_id: 'exec-2',
      status: 'running',
    });
  }),

  // Execution endpoints
  http.get(`${baseUrl}/api/executions`, () => {
    return HttpResponse.json([mockExecution]);
  }),

  http.get(`${baseUrl}/api/executions/:id`, ({ params }) => {
    const { id } = params;
    if (id === 'exec-1') {
      return HttpResponse.json(mockExecution);
    }
    return new HttpResponse(null, { status: 404 });
  }),
];
