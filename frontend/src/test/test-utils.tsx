/* eslint-disable react-refresh/only-export-components */
// Custom render function with providers
import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';

// Create a new QueryClient for each test
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Turn off retries for tests
        retry: false,
        // Use shorter timeouts for tests
        staleTime: 0,
        cacheTime: 0,
      },
    },
    logger: {
      // Silence query errors in tests
      log: console.log,
      warn: console.warn,
      error: () => {},
    },
  });
}

interface AllProvidersProps {
  children: React.ReactNode;
}

// All providers wrapper
export function AllProviders({ children }: AllProvidersProps) {
  const queryClient = createTestQueryClient();

  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <ConfigProvider
          theme={{
            token: {
              colorPrimary: '#4f46e5',
            },
          }}
        >
          {children}
        </ConfigProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
}

// Custom render function
const customRender = (ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) =>
  render(ui, { wrapper: AllProviders, ...options });

// Re-export everything
export * from '@testing-library/react';
export { customRender as render };

// Test data factories
export const createMockWorkflow = (overrides = {}) => ({
  id: '1',
  name: 'Test Workflow',
  description: 'A test workflow',
  path: '/workflows/test.yaml',
  version: '1.0.0',
  inputs: {
    input1: { type: 'string', required: true },
  },
  is_public: true,
  username: 'testuser',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

export const createMockExecution = (overrides = {}) => ({
  id: 'exec-1',
  workflow_id: '1',
  workflow_name: 'Test Workflow',
  status: 'completed',
  inputs: { input1: 'test' },
  outputs: { result: 'success' },
  created_at: new Date().toISOString(),
  completed_at: new Date().toISOString(),
  error: null,
  node_executions: [],
  ...overrides,
});
