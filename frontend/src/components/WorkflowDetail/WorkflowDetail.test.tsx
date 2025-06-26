import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '../../test/test-utils';
import { WorkflowDetail } from './WorkflowDetail';
import { server } from '../../test/mocks/server';
import { http, HttpResponse } from 'msw';
import { mockWorkflowDetail } from '../../test/mocks/handlers';

describe('WorkflowDetail', () => {
  const mockOnBack = vi.fn();

  beforeEach(() => {
    mockOnBack.mockClear();
  });

  it('shows loading state while fetching workflow', () => {
    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    expect(screen.getByRole('img', { name: /loading/i })).toBeInTheDocument();
  });

  it('renders workflow details after loading', async () => {
    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    // Wait for workflow to load
    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Check workflow info
    expect(screen.getByText('A test workflow for unit testing')).toBeInTheDocument();
    expect(screen.getByText('v1.0.0')).toBeInTheDocument();
    expect(screen.getByText('testuser')).toBeInTheDocument();
  });

  it('displays workflow tabs', async () => {
    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Check tabs
    expect(screen.getByRole('tab', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'YAML Editor' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'DAG View' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Test Runner' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Executions' })).toBeInTheDocument();
  });

  it('shows workflow inputs and outputs in overview tab', async () => {
    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Check inputs section
    expect(screen.getByText('Inputs')).toBeInTheDocument();
    expect(screen.getByText('company')).toBeInTheDocument();
    expect(screen.getByText('string')).toBeInTheDocument();
    expect(screen.getByText('Required')).toBeInTheDocument();

    // Check outputs section
    expect(screen.getByText('Outputs')).toBeInTheDocument();
    expect(screen.getByText('result')).toBeInTheDocument();
    expect(screen.getByText('analyze')).toBeInTheDocument();
  });

  it('displays node information in overview', async () => {
    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Check nodes section
    expect(screen.getByText('Nodes')).toBeInTheDocument();
    expect(screen.getByText('fetch_data')).toBeInTheDocument();
    expect(screen.getByText('http')).toBeInTheDocument();
    expect(screen.getByText('analyze')).toBeInTheDocument();
    expect(screen.getByText('llm')).toBeInTheDocument();
  });

  it('switches to YAML editor tab and displays content', async () => {
    const user = userEvent.setup();
    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Click YAML Editor tab
    await user.click(screen.getByRole('tab', { name: 'YAML Editor' }));

    // Should show YAML content
    await waitFor(() => {
      expect(screen.getByTestId('monaco-editor')).toHaveValue(mockWorkflowDetail.content);
    });
  });

  it('handles run workflow action', async () => {
    const user = userEvent.setup();
    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Click run button
    const runButton = screen.getByRole('button', { name: /run/i });
    await user.click(runButton);

    // Should open run workflow modal
    await waitFor(() => {
      expect(screen.getByText('Run Workflow: Test Workflow 1')).toBeInTheDocument();
    });
  });

  it('handles delete workflow action', async () => {
    const user = userEvent.setup();
    let deleteRequested = false;

    server.use(
      http.delete('http://localhost:8000/api/workflows/:id', () => {
        deleteRequested = true;
        return new HttpResponse(null, { status: 204 });
      })
    );

    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Click delete button
    const deleteButton = screen.getByRole('button', { name: /delete/i });
    await user.click(deleteButton);

    // Confirm deletion in modal
    const confirmButton = await screen.findByRole('button', { name: /ok/i });
    await user.click(confirmButton);

    // Should delete and go back
    await waitFor(() => {
      expect(deleteRequested).toBe(true);
      expect(mockOnBack).toHaveBeenCalled();
    });
  });

  it('handles save workflow changes', async () => {
    const user = userEvent.setup();
    let savedContent: string | null = null;

    server.use(
      http.put('http://localhost:8000/api/workflows/:id', async ({ request }) => {
        const body = await request.json();
        savedContent = body.content;
        return HttpResponse.json({ ...mockWorkflowDetail, content: savedContent });
      })
    );

    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Switch to YAML editor
    await user.click(screen.getByRole('tab', { name: 'YAML Editor' }));

    // Modify content
    const editor = screen.getByTestId('monaco-editor');
    const newContent = mockWorkflowDetail.content + '\n# Modified';
    await user.clear(editor);
    await user.type(editor, newContent);

    // Save changes
    const saveButton = screen.getByRole('button', { name: /save/i });
    await user.click(saveButton);

    // Should save the new content
    await waitFor(() => {
      expect(savedContent).toBe(newContent);
    });
  });

  it('shows error when workflow not found', async () => {
    server.use(
      http.get('http://localhost:8000/api/workflows/:id', () => {
        return HttpResponse.json({ detail: 'Workflow not found' }, { status: 404 });
      })
    );

    render(<WorkflowDetail workflowId="999" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText(/workflow not found/i)).toBeInTheDocument();
    });
  });

  it('handles back navigation', async () => {
    const user = userEvent.setup();
    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Click back button
    const backButton = screen.getByRole('button', { name: /back/i });
    await user.click(backButton);

    expect(mockOnBack).toHaveBeenCalled();
  });

  it('shows execution history in executions tab', async () => {
    const user = userEvent.setup();
    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Click Executions tab
    await user.click(screen.getByRole('tab', { name: 'Executions' }));

    // Should show execution list
    await waitFor(() => {
      expect(screen.getByText('exec-1')).toBeInTheDocument();
      expect(screen.getByText('completed')).toBeInTheDocument();
    });
  });

  it('handles workflow validation', async () => {
    const user = userEvent.setup();
    render(<WorkflowDetail workflowId="1" onBack={mockOnBack} />);

    await waitFor(() => {
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
    });

    // Switch to YAML editor
    await user.click(screen.getByRole('tab', { name: 'YAML Editor' }));

    // Click validate button
    const validateButton = screen.getByRole('button', { name: /validate/i });
    await user.click(validateButton);

    // Should show validation result
    await waitFor(() => {
      expect(screen.getByText(/validation passed/i)).toBeInTheDocument();
    });
  });
});
