import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '../../test/test-utils';
import { RunWorkflowModal } from './RunWorkflowModal';
import { server } from '../../test/mocks/server';
import { http, HttpResponse } from 'msw';

describe('RunWorkflowModal', () => {
  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();

  const mockWorkflow = {
    id: '1',
    name: 'Test Workflow',
    inputs: {
      company: {
        type: 'string',
        required: true,
        description: 'Company name to analyze',
      },
      location: {
        type: 'string',
        required: false,
        default: 'USA',
        description: 'Company location',
      },
      includeFinancials: {
        type: 'boolean',
        required: false,
        default: false,
        description: 'Include financial analysis',
      },
    },
  };

  beforeEach(() => {
    mockOnClose.mockClear();
    mockOnSuccess.mockClear();
  });

  it('renders modal with workflow name and inputs', () => {
    render(
      <RunWorkflowModal
        visible={true}
        workflow={mockWorkflow}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    // Check modal title
    expect(screen.getByText('Run Workflow: Test Workflow')).toBeInTheDocument();

    // Check input fields
    expect(screen.getByLabelText(/company/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/location/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/include financials/i)).toBeInTheDocument();
  });

  it('shows required indicator for required fields', () => {
    render(
      <RunWorkflowModal
        visible={true}
        workflow={mockWorkflow}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    const companyField = screen.getByLabelText(/company/i).closest('.ant-form-item');
    expect(companyField).toHaveTextContent('*');

    const locationField = screen.getByLabelText(/location/i).closest('.ant-form-item');
    expect(locationField).not.toHaveTextContent('*');
  });

  it('pre-fills default values for optional fields', () => {
    render(
      <RunWorkflowModal
        visible={true}
        workflow={mockWorkflow}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    const locationInput = screen.getByLabelText(/location/i);
    expect(locationInput).toHaveValue('USA');

    const financialsCheckbox = screen.getByLabelText(/include financials/i);
    expect(financialsCheckbox).not.toBeChecked();
  });

  it('validates required fields before submission', async () => {
    const user = userEvent.setup();
    render(
      <RunWorkflowModal
        visible={true}
        workflow={mockWorkflow}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    // Try to submit without filling required field
    const runButton = screen.getByRole('button', { name: /run workflow/i });
    await user.click(runButton);

    // Should show validation error
    await waitFor(() => {
      expect(screen.getByText(/please input/i)).toBeInTheDocument();
    });

    // Should not call API
    expect(mockOnSuccess).not.toHaveBeenCalled();
  });

  it('submits workflow execution with correct inputs', async () => {
    const user = userEvent.setup();
    let capturedBody: any;

    server.use(
      http.post('http://localhost:8000/api/workflows/:id/execute', async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({
          execution_id: 'exec-123',
          status: 'running',
        });
      })
    );

    render(
      <RunWorkflowModal
        visible={true}
        workflow={mockWorkflow}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    // Fill in inputs
    const companyInput = screen.getByLabelText(/company/i);
    await user.type(companyInput, 'Acme Corp');

    const locationInput = screen.getByLabelText(/location/i);
    await user.clear(locationInput);
    await user.type(locationInput, 'Boston');

    const financialsCheckbox = screen.getByLabelText(/include financials/i);
    await user.click(financialsCheckbox);

    // Submit form
    const runButton = screen.getByRole('button', { name: /run workflow/i });
    await user.click(runButton);

    // Check submitted data
    await waitFor(() => {
      expect(capturedBody).toEqual({
        company: 'Acme Corp',
        location: 'Boston',
        includeFinancials: true,
      });
    });

    expect(mockOnSuccess).toHaveBeenCalledWith('exec-123');
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('handles different input types correctly', () => {
    const complexWorkflow = {
      id: '2',
      name: 'Complex Workflow',
      inputs: {
        text: { type: 'string', required: true },
        number: { type: 'number', required: true },
        boolean: { type: 'boolean', required: true },
        array: { type: 'array', required: true },
        object: { type: 'object', required: true },
      },
    };

    render(
      <RunWorkflowModal
        visible={true}
        workflow={complexWorkflow}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    // String input
    expect(screen.getByLabelText(/text/i)).toHaveAttribute('type', 'text');

    // Number input
    expect(screen.getByLabelText(/number/i)).toHaveAttribute('type', 'number');

    // Boolean input (checkbox)
    expect(screen.getByLabelText(/boolean/i)).toHaveAttribute('type', 'checkbox');

    // Array and object inputs (textarea for JSON)
    const arrayInput = screen.getByLabelText(/array/i);
    expect(arrayInput.tagName).toBe('TEXTAREA');

    const objectInput = screen.getByLabelText(/object/i);
    expect(objectInput.tagName).toBe('TEXTAREA');
  });

  it('shows loading state during submission', async () => {
    const user = userEvent.setup();

    // Delay the response to see loading state
    server.use(
      http.post('http://localhost:8000/api/workflows/:id/execute', async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json({ execution_id: 'exec-123', status: 'running' });
      })
    );

    render(
      <RunWorkflowModal
        visible={true}
        workflow={mockWorkflow}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    // Fill required field
    await user.type(screen.getByLabelText(/company/i), 'Acme Corp');

    // Submit
    const runButton = screen.getByRole('button', { name: /run workflow/i });
    await user.click(runButton);

    // Check loading state
    expect(runButton).toBeDisabled();
    expect(runButton).toHaveAttribute('aria-busy', 'true');

    // Wait for completion
    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });

  it('handles API errors gracefully', async () => {
    const user = userEvent.setup();

    server.use(
      http.post('http://localhost:8000/api/workflows/:id/execute', () => {
        return HttpResponse.json(
          { detail: 'Invalid input: company name too long' },
          { status: 400 }
        );
      })
    );

    render(
      <RunWorkflowModal
        visible={true}
        workflow={mockWorkflow}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    // Fill and submit
    await user.type(screen.getByLabelText(/company/i), 'Very Long Company Name');
    await user.click(screen.getByRole('button', { name: /run workflow/i }));

    // Should show error message
    await waitFor(() => {
      expect(screen.getByText(/Invalid input: company name too long/i)).toBeInTheDocument();
    });

    // Should not close modal
    expect(mockOnClose).not.toHaveBeenCalled();
    expect(mockOnSuccess).not.toHaveBeenCalled();
  });

  it('closes modal when cancel button is clicked', async () => {
    const user = userEvent.setup();
    render(
      <RunWorkflowModal
        visible={true}
        workflow={mockWorkflow}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalled();
    expect(mockOnSuccess).not.toHaveBeenCalled();
  });

  it('validates JSON input for array and object types', async () => {
    const user = userEvent.setup();
    const jsonWorkflow = {
      id: '3',
      name: 'JSON Workflow',
      inputs: {
        data: { type: 'array', required: true },
      },
    };

    render(
      <RunWorkflowModal
        visible={true}
        workflow={jsonWorkflow}
        onClose={mockOnClose}
        onSuccess={mockOnSuccess}
      />
    );

    const dataInput = screen.getByLabelText(/data/i);

    // Try invalid JSON
    await user.type(dataInput, 'invalid json');
    await user.click(screen.getByRole('button', { name: /run workflow/i }));

    // Should show JSON validation error
    await waitFor(() => {
      expect(screen.getByText(/invalid json/i)).toBeInTheDocument();
    });

    // Try valid JSON
    await user.clear(dataInput);
    await user.type(dataInput, '["item1", "item2"]');
    await user.click(screen.getByRole('button', { name: /run workflow/i }));

    // Should succeed
    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });
});
