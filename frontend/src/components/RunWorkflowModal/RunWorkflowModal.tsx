import React, { useState } from 'react';
import { Modal, Form, Input, InputNumber, Switch, Button, Alert, Space } from 'antd';
import { useNavigate } from 'react-router-dom';
import type { WorkflowDetail, ExecutionInput } from '../../types/workflow';
import { workflowAPI } from '../../api/client';

interface RunWorkflowModalProps {
  workflow: WorkflowDetail;
  open: boolean;
  onClose: () => void;
}

export const RunWorkflowModal: React.FC<RunWorkflowModalProps> = ({ workflow, open, onClose }) => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    try {
      setLoading(true);
      setError(null);

      // Get form values
      const values = await form.validateFields();

      // Convert form values to match API expectations
      const inputs: ExecutionInput = {};
      Object.entries(values).forEach(([key, value]) => {
        // Only include non-undefined values
        if (value !== undefined) {
          // Parse JSON for object/array types
          const workflowData = workflow.parsed || workflow.workflow || workflow;
          const inputDef = workflowData.inputs?.[key];
          if (inputDef && (inputDef.type === 'object' || inputDef.type === 'array')) {
            try {
              inputs[key] = JSON.parse(value as string);
            } catch {
              inputs[key] = value;
            }
          } else {
            inputs[key] = value;
          }
        }
      });

      // Run the workflow
      const response = await workflowAPI.run(workflow.path || workflow.id, inputs);

      // Close modal and navigate to execution detail
      onClose();
      navigate(`/executions/${response.execution_id}`);
    } catch (err) {
      console.error('Failed to run workflow:', err);
      setError(err instanceof Error ? err.message : 'Failed to run workflow');
    } finally {
      setLoading(false);
    }
  };

  const renderInputField = (name: string, input: any) => {
    const rules = input.required ? [{ required: true, message: `${name} is required` }] : [];

    switch (input.type) {
      case 'string':
        return (
          <Form.Item key={name} name={name} label={name} rules={rules} initialValue={input.default}>
            <Input placeholder={`Enter ${name}`} />
          </Form.Item>
        );

      case 'number':
        return (
          <Form.Item key={name} name={name} label={name} rules={rules} initialValue={input.default}>
            <InputNumber style={{ width: '100%' }} placeholder={`Enter ${name}`} />
          </Form.Item>
        );

      case 'boolean':
        return (
          <Form.Item
            key={name}
            name={name}
            label={name}
            valuePropName="checked"
            initialValue={input.default ?? false}
          >
            <Switch />
          </Form.Item>
        );

      case 'object':
      case 'array':
        return (
          <Form.Item
            key={name}
            name={name}
            label={name}
            rules={[
              ...rules,
              {
                validator: (_, value) => {
                  if (!value) return Promise.resolve();
                  try {
                    JSON.parse(value);
                    return Promise.resolve();
                  } catch {
                    return Promise.reject(new Error('Must be valid JSON'));
                  }
                },
              },
            ]}
            initialValue={input.default ? JSON.stringify(input.default, null, 2) : ''}
          >
            <Input.TextArea
              rows={4}
              placeholder={`Enter ${input.type === 'object' ? 'JSON object' : 'JSON array'}`}
            />
          </Form.Item>
        );

      default:
        return (
          <Form.Item key={name} name={name} label={name} rules={rules} initialValue={input.default}>
            <Input placeholder={`Enter ${name} (${input.type})`} />
          </Form.Item>
        );
    }
  };

  return (
    <Modal
      title={`Run Workflow: ${(workflow.parsed || workflow.workflow || workflow).name}`}
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Cancel
        </Button>,
        <Button key="run" type="primary" loading={loading} onClick={handleSubmit}>
          Run Workflow
        </Button>,
      ]}
      width={600}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {error && (
          <Alert
            message="Error"
            description={error}
            type="error"
            closable
            onClose={() => setError(null)}
          />
        )}

        <Form form={form} layout="vertical">
          {Object.entries((workflow.parsed || workflow.workflow || workflow).inputs || {}).map(
            ([name, input]) => renderInputField(name, input)
          )}

          {Object.keys((workflow.parsed || workflow.workflow || workflow).inputs || {}).length ===
            0 && (
            <Alert
              message="No inputs required"
              description="This workflow doesn't require any inputs. Click 'Run Workflow' to start execution."
              type="info"
            />
          )}
        </Form>
      </Space>
    </Modal>
  );
};
