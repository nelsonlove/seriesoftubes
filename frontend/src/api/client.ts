import axios from 'axios';
import type {
  WorkflowSummary,
  WorkflowDetail,
  ExecutionInput,
  ExecutionResponse,
  ExecutionDetail,
  ExecutionProgress,
} from '../types/workflow';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const workflowAPI = {
  // List all workflows
  list: async (params?: { tag?: string; search?: string }) => {
    const response = await api.get<WorkflowSummary[]>('/workflows', { params });
    return response.data;
  },

  // Get workflow details
  get: async (path: string) => {
    const response = await api.get<WorkflowDetail>(`/workflows/${encodeURIComponent(path)}`);
    return response.data;
  },

  // Run a workflow
  run: async (path: string, inputs: ExecutionInput) => {
    const response = await api.post<ExecutionResponse>(
      `/workflows/${encodeURIComponent(path)}/run`,
      inputs
    );
    return response.data;
  },
};

export const executionAPI = {
  // List all executions
  list: async (params?: { workflow?: string; status?: string; limit?: number }) => {
    const response = await api.get<ExecutionResponse[]>('/executions', { params });
    return response.data;
  },

  // Get execution details
  get: async (id: string) => {
    const response = await api.get<ExecutionDetail>(`/executions/${id}`);
    return response.data;
  },

  // Stream execution progress
  stream: (id: string, onProgress: (progress: ExecutionProgress) => void) => {
    const eventSource = new EventSource(`/api/executions/${id}/stream`);

    eventSource.onmessage = (event) => {
      const progress = JSON.parse(event.data) as ExecutionProgress;
      onProgress(progress);
    };

    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      eventSource.close();
    };

    return eventSource;
  },
};

export default api;
