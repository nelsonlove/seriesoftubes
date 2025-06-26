import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '../../test/test-utils';
import { WorkflowList } from './WorkflowList';
import { server } from '../../test/mocks/server';
import { http, HttpResponse } from 'msw';

describe('WorkflowList', () => {
  const mockOnSelectWorkflow = vi.fn();

  beforeEach(() => {
    mockOnSelectWorkflow.mockClear();
  });

  it('renders workflow list with loading state', async () => {
    render(<WorkflowList onSelectWorkflow={mockOnSelectWorkflow} />);

    // Should show loading spinner initially
    expect(screen.getByRole('img', { name: /loading/i })).toBeInTheDocument();
  });

  it('renders workflows after loading', async () => {
    render(<WorkflowList onSelectWorkflow={mockOnSelectWorkflow} />);

    // Wait for workflows to load
    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    expect(screen.getByText('Test Workflow 2')).toBeInTheDocument();
    expect(screen.getByText('2 workflows')).toBeInTheDocument();
  });

  it('handles search functionality', async () => {
    const user = userEvent.setup();
    render(<WorkflowList onSelectWorkflow={mockOnSelectWorkflow} />);

    // Wait for workflows to load
    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Search for workflow
    const searchInput = screen.getByPlaceholderText(/search workflows/i);
    await user.type(searchInput, 'Workflow 1');

    // Should filter to only matching workflow
    expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    expect(screen.queryByText('Test Workflow 2')).not.toBeInTheDocument();
    expect(screen.getByText('1 workflow')).toBeInTheDocument();
  });

  it('handles workflow selection', async () => {
    const user = userEvent.setup();
    render(<WorkflowList onSelectWorkflow={mockOnSelectWorkflow} />);

    // Wait for workflows to load
    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Click on workflow card
    const workflowCard = screen.getByText('Test Workflow 1').closest('div[role="button"]');
    await user.click(workflowCard!);

    expect(mockOnSelectWorkflow).toHaveBeenCalledWith('/workflows/test-workflow-1.yaml');
  });

  it('displays workflow metadata correctly', async () => {
    render(<WorkflowList onSelectWorkflow={mockOnSelectWorkflow} />);

    // Wait for workflows to load
    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Check metadata display
    expect(screen.getByText('A test workflow for unit testing')).toBeInTheDocument();
    expect(screen.getByText('Public')).toBeInTheDocument();
    expect(screen.getByText('2 inputs')).toBeInTheDocument();
    expect(screen.getByText('v1.0.0')).toBeInTheDocument();
    expect(screen.getByText('testuser')).toBeInTheDocument();
  });

  it('handles error state', async () => {
    // Override handler to return error
    server.use(
      http.get('http://localhost:8000/api/workflows', () => {
        return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
      })
    );

    render(<WorkflowList onSelectWorkflow={mockOnSelectWorkflow} />);

    // Wait for error message
    await waitFor(() => {
      expect(screen.getByText(/failed to load workflows/i)).toBeInTheDocument();
    });
  });

  it('opens new workflow modal when clicking New Workflow button', async () => {
    const user = userEvent.setup();
    render(<WorkflowList onSelectWorkflow={mockOnSelectWorkflow} />);

    // Wait for workflows to load
    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Click New Workflow button
    const newWorkflowButton = screen.getByRole('button', { name: /new workflow/i });
    await user.click(newWorkflowButton);

    // Modal should appear
    await waitFor(() => {
      expect(screen.getByText('New Workflow')).toBeInTheDocument();
      expect(screen.getByText('Create New')).toBeInTheDocument();
      expect(screen.getByText('Upload File')).toBeInTheDocument();
    });
  });

  it('refreshes workflow list when clicking refresh button', async () => {
    const user = userEvent.setup();
    let callCount = 0;

    // Track API calls
    server.use(
      http.get('http://localhost:8000/api/workflows', () => {
        callCount++;
        return HttpResponse.json([
          {
            id: callCount.toString(),
            name: `Test Workflow ${callCount}`,
            description: 'A test workflow',
            path: `/workflows/test-${callCount}.yaml`,
            version: '1.0.0',
            inputs: {},
            is_public: true,
            username: 'testuser',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ]);
      })
    );

    render(<WorkflowList onSelectWorkflow={mockOnSelectWorkflow} />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Click refresh button
    const refreshButton = screen.getByRole('button', { name: /refresh workflows/i });
    await user.click(refreshButton);

    // Should show updated data
    await waitFor(() => {
      expect(screen.getByText('Test Workflow 2')).toBeInTheDocument();
    });

    expect(callCount).toBe(2);
  });

  it('filters workflows by input fields', async () => {
    const user = userEvent.setup();
    render(<WorkflowList onSelectWorkflow={mockOnSelectWorkflow} />);

    // Wait for workflows to load
    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Search by input field name
    const searchInput = screen.getByPlaceholderText(/search workflows/i);
    await user.type(searchInput, 'company');

    // Should show only workflow with 'company' input
    expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    expect(screen.queryByText('Test Workflow 2')).not.toBeInTheDocument();
  });
});
