import axios from 'axios';
import type {
  WorkflowSummary,
  WorkflowDetail,
  ExecutionInput,
  ExecutionResponse,
  ExecutionDetail,
} from '../types/workflow';
import { useAuthStore } from '../stores/auth';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle 401 responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear auth and redirect to login
      useAuthStore.getState().logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Helper to parse YAML and extract inputs
const parseWorkflowInputs = (yamlContent: string): Record<string, any> => {
  try {
    // Simple regex to extract inputs section
    // This is a basic implementation - in production you'd use a proper YAML parser
    const inputsMatch = yamlContent.match(/inputs:\s*\n((?:\s{2,}.*\n)*)/);
    if (!inputsMatch) return {};
    
    // For now, return empty object - the backend should ideally parse this
    return {};
  } catch {
    return {};
  }
};

export const workflowAPI = {
  // List all workflows
  list: async (params?: { tag?: string; search?: string }) => {
    const response = await api.get<any[]>('/workflows', { params });
    // Transform the response to match our WorkflowSummary type
    return response.data.map(wf => ({
      ...wf,
      path: wf.id, // Use ID as path for now
      inputs: parseWorkflowInputs(wf.yaml_content),
    })) as WorkflowSummary[];
  },

  // Get workflow details
  get: async (path: string) => {
    const response = await api.get<WorkflowDetail>(`/workflows/${encodeURIComponent(path)}`);
    return response.data;
  },

  // Create a new workflow
  create: async (yamlContent: string, isPublic: boolean = false) => {
    const response = await api.post<{
      id: string;
      name: string;
      version: string;
      description: string | null;
      user_id: string;
      username: string;
      is_public: boolean;
      created_at: string;
      updated_at: string;
    }>('/workflows', {
      yaml_content: yamlContent,
      is_public: isPublic,
    });
    return response.data;
  },

  // Upload a workflow file
  uploadFile: async (file: File, isPublic: boolean = false) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post<{
      id: string;
      name: string;
      version: string;
      description: string | null;
      user_id: string;
      username: string;
      is_public: boolean;
      created_at: string;
      updated_at: string;
    }>(`/workflows/upload?is_public=${isPublic}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Update a workflow
  update: async (id: string, yamlContent: string, isPublic?: boolean) => {
    const response = await api.put<WorkflowDetail>(`/workflows/${id}`, {
      yaml_content: yamlContent,
      is_public: isPublic,
    });
    return response.data;
  },

  // Delete a workflow
  delete: async (id: string) => {
    const response = await api.delete<{ message: string }>(`/workflows/${id}`);
    return response.data;
  },

  // Download a workflow
  download: async (id: string, format: 'yaml' | 'tubes' = 'yaml') => {
    const response = await api.get(`/workflows/${id}/download`, {
      params: { format },
      responseType: 'blob',
    });
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

  // Get raw YAML content
  getRaw: async (path: string) => {
    // Use the root-level endpoint, not under /api
    const response = await axios.get<{ content: string; path: string; modified: number }>(
      `/workflows/${encodeURIComponent(path)}/raw`
    );
    return response.data;
  },

  // Update raw YAML content
  updateRaw: async (path: string, content: string, expectedModified?: number) => {
    // Use the root-level endpoint, not under /api
    const response = await axios.put<{
      success: boolean;
      path: string;
      modified: number;
      workflow: { name: string; version: string };
    }>(`/workflows/${encodeURIComponent(path)}/raw`, {
      content,
      expected_modified: expectedModified,
    });
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
