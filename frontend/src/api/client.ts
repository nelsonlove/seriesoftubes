import axios from 'axios';
import type {
  WorkflowSummary,
  WorkflowDetail,
  WorkflowResponse,
  ExecutionInput,
  ExecutionResponse,
  ExecutionDetail,
} from '../types/workflow';
import { useAuthStore } from '../stores/auth';

const api = axios.create({
  baseURL: '', // No base URL so we can use both /api and /auth
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
    // Don't redirect on login/register attempts
    const isAuthEndpoint = error.config?.url?.includes('/auth/login') || 
                          error.config?.url?.includes('/auth/register');
    
    if (error.response?.status === 401 && !isAuthEndpoint) {
      // Clear auth and redirect to login for non-auth endpoints
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
    const response = await api.get<any[]>('/api/workflows', { params });
    // Transform the response to match our WorkflowSummary type
    return response.data.map((wf) => ({
      ...wf,
      path: wf.id, // Use ID as path for now
      inputs: parseWorkflowInputs(wf.yaml_content),
    })) as WorkflowSummary[];
  },

  // Get workflow details
  get: async (path: string) => {
    const response = await api.get<WorkflowDetail>(`/api/workflows/${encodeURIComponent(path)}`);
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
    }>('/api/workflows', {
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
    }>(`/api/workflows/upload?is_public=${isPublic}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Update a workflow
  update: async (id: string, yamlContent: string, isPublic?: boolean) => {
    const response = await api.put<WorkflowDetail>(`/api/workflows/${id}`, {
      yaml_content: yamlContent,
      is_public: isPublic,
    });
    return response.data;
  },

  // Delete a workflow
  delete: async (id: string) => {
    const response = await api.delete<{ message: string }>(`/api/workflows/${id}`);
    return response.data;
  },

  // Download a workflow
  download: async (id: string, format: 'yaml' | 'tubes' = 'yaml') => {
    const response = await api.get(`/api/workflows/${id}/download`, {
      params: { format },
      responseType: 'blob',
    });
    return response.data;
  },

  // Run a workflow
  run: async (path: string, inputs: ExecutionInput) => {
    const response = await api.post<{ execution_id: string; status: string; message: string }>(
      `/api/workflows/${encodeURIComponent(path)}/run`,
      { inputs }
    );
    return response.data;
  },

  // Get raw YAML content
  getRaw: async (workflowId: string) => {
    // Use the existing workflow detail endpoint to get YAML content
    const response = await api.get<WorkflowDetail>(`/api/workflows/${encodeURIComponent(workflowId)}`);
    return {
      content: response.data.yaml_content,
      path: workflowId,
      modified: new Date(response.data.updated_at).getTime(),
    };
  },

  // Update raw YAML content
  updateRaw: async (workflowId: string, content: string) => {
    // Use the existing workflow update endpoint
    const response = await api.put<WorkflowResponse>(
      `/api/workflows/${encodeURIComponent(workflowId)}`,
      {
        yaml_content: content,
      }
    );
    return {
      success: true,
      path: workflowId,
      modified: new Date(response.data.updated_at).getTime(),
      workflow: { name: response.data.name, version: response.data.version },
    };
  },
};

export const executionAPI = {
  // List all executions
  list: async (params?: { workflow?: string; status?: string; limit?: number }) => {
    const response = await api.get<ExecutionResponse[]>('/api/executions', { params });
    return response.data;
  },

  // Get execution details
  get: async (id: string) => {
    const response = await api.get<ExecutionDetail>(`/api/executions/${id}`);
    return response.data;
  },

  // Stream execution progress
  stream: (id: string, onUpdate: (data: any) => void) => {
    const token = useAuthStore.getState().token;
    // Use API URL from environment or default
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const url = token
      ? `${apiUrl}/api/executions/${id}/stream?token=${encodeURIComponent(token)}`
      : `${apiUrl}/api/executions/${id}/stream`;

    console.log('Connecting to SSE URL:', url);
    const eventSource = new EventSource(url);

    // Listen for default message events (no event type specified)
    eventSource.onmessage = (event) => {
      console.log('SSE message event:', event.data);
      try {
        // Try to parse as JSON, handling whitespace and formatting
        let data;
        try {
          // Clean up the event data - remove extra whitespace, newlines, and SSE prefix
          let cleanedData = event.data.trim();

          // Remove 'data: ' prefix if present (sometimes SSE includes this)
          if (cleanedData.startsWith('data: ')) {
            cleanedData = cleanedData.substring(6).trim();
          }

          data = JSON.parse(cleanedData);
          // Check if this is a complete event and close the connection
          if (data.type === 'complete' || data.done === true) {
            console.log('SSE stream complete, closing connection');
            eventSource.close();
          }
        } catch (parseError) {
          console.warn('Failed to parse SSE data as JSON:', parseError, 'Raw data:', event.data);
          // If it's not valid JSON, try to extract JSON from the message
          const trimmed = event.data.trim();
          if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
            try {
              data = JSON.parse(trimmed);
            } catch {
              data = { message: event.data };
            }
          } else {
            data = { message: event.data };
          }
        }
        onUpdate(data);
      } catch (error) {
        console.error('Failed to handle SSE message:', error);
      }
    };

    eventSource.addEventListener('update', (event) => {
      console.log('SSE update event:', event.data);
      try {
        const data = JSON.parse(event.data);
        onUpdate(data);
      } catch (error) {
        console.error('Failed to parse SSE data:', error);
      }
    });

    eventSource.addEventListener('complete', (event) => {
      console.log('SSE complete event:', event.data);
      try {
        const data = JSON.parse(event.data);
        onUpdate(data);
        eventSource.close();
      } catch (error) {
        console.error('Failed to parse SSE complete data:', error);
      }
    });

    eventSource.onopen = (event) => {
      console.log('SSE connection opened:', event);
    };

    eventSource.onerror = (error) => {
      console.error('SSE error:', error, 'readyState:', eventSource.readyState);
      if (eventSource.readyState === EventSource.CONNECTING) {
        console.log('SSE reconnecting...');
      } else if (eventSource.readyState === EventSource.CLOSED) {
        console.log('SSE connection closed');
      }
      // Don't close on error - let it retry
    };

    return eventSource;
  },
};

export interface DocFile {
  path: string;
  title: string;
  category: string;
}

export interface DocsListResponse {
  success: boolean;
  message: string;
  data: DocFile[];
}

export const docsAPI = {
  // List all documentation files
  list: async () => {
    const response = await api.get<DocsListResponse>('/api/docs/');
    return response.data;
  },

  // Get documentation content
  getContent: async (filePath: string) => {
    const response = await api.get<string>(`/api/docs/${filePath}`, {
      responseType: 'text',
    });
    return response.data;
  },
};

export interface FileInfo {
  file_id: string;
  filename: string;
  size: number;
  content_type: string;
  uploaded_at: string;
  is_public: boolean;
  storage_key?: string;
}

export interface FilesListResponse {
  success: boolean;
  files: FileInfo[];
  total: number;
}

export const filesAPI = {
  // List user files
  list: async (params?: { prefix?: string; limit?: number }) => {
    const response = await api.get<FilesListResponse>('/api/files', { params });
    return response.data;
  },

  // Upload a file
  upload: async (file: File, isPublic: boolean = false) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/api/files/upload', formData, {
      params: { is_public: isPublic },
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Download a file
  download: async (fileId: string) => {
    const response = await api.get(`/api/files/${fileId}/download`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Delete a file
  delete: async (fileId: string) => {
    const response = await api.delete(`/api/files/${fileId}`);
    return response.data;
  },
};

export default api;
