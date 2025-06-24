import axios from 'axios';
import type {
  WorkflowSummary,
  WorkflowDetail,
  ExecutionInput,
  ExecutionResponse,
  ExecutionDetail,
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
    const response = await api.post<{ execution_id: string; status: string; message: string }>(
      `/workflows/${encodeURIComponent(path)}/run`,
      { inputs }
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
  stream: (id: string, onUpdate: (data: any) => void) => {
    const eventSource = new EventSource(`/api/executions/${id}/stream`);

    eventSource.addEventListener('update', (event) => {
      try {
        const data = JSON.parse(event.data);
        onUpdate(data);
      } catch (error) {
        console.error('Failed to parse SSE data:', error);
      }
    });

    eventSource.addEventListener('complete', (event) => {
      try {
        const data = JSON.parse(event.data);
        onUpdate(data);
        eventSource.close();
      } catch (error) {
        console.error('Failed to parse SSE complete data:', error);
      }
    });

    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      eventSource.close();
    };

    return eventSource;
  },
};

export default api;
