import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Spin,
  Typography,
  Space,
  Tag,
  Descriptions,
  Alert,
  Button,
  Progress,
  Collapse,
} from 'antd';
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { executionAPI } from '../../api/client';
import { useExecutionStore } from '../../stores/execution';
import type { ExecutionProgress } from '../../types/workflow';

const { Title, Text } = Typography;
const { Panel } = Collapse;

export const ExecutionDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [, setEventSource] = useState<EventSource | null>(null);

  const { setExecution, updateProgress } = useExecutionStore();
  const execution = useExecutionStore((state) => state.executions[id || '']);

  // Fetch initial execution data
  const {
    data: initialData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['execution', id],
    queryFn: () => executionAPI.get(id!),
    enabled: !!id,
  });

  // Update store when data is loaded
  React.useEffect(() => {
    if (initialData && id) {
      // Ensure the data has an id field
      const executionData = {
        ...initialData,
        id: initialData.id || initialData.execution_id || id,
      };
      setExecution(executionData);
    }
  }, [initialData, id, setExecution]);

  // Set up SSE connection for real-time updates
  useEffect(() => {
    if (!id || !execution) return;

    // Only set up SSE for running executions
    if (execution.status !== 'running' && execution.status !== 'pending') {
      return;
    }

    const es = executionAPI.stream(id, (data: any) => {
      // Update execution with latest data
      if (data.status) {
        setExecution({
          ...execution,
          status: data.status,
          outputs: data.outputs,
          errors: data.errors,
        });
      }

      // Update progress for each node
      if (data.progress) {
        Object.entries(data.progress).forEach(([node, statusOrProgress]) => {
          // Handle both string status and full progress object
          if (typeof statusOrProgress === 'string') {
            updateProgress(id, node, {
              node,
              status: statusOrProgress as any,
            });
          } else {
            updateProgress(id, node, statusOrProgress as ExecutionProgress);
          }
        });
      }
    });

    setEventSource(es);

    return () => {
      es.close();
    };
  }, [id, execution, updateProgress]);

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error || !initialData) {
    return (
      <Alert message="Error" description="Failed to load execution details" type="error" showIcon />
    );
  }

  const executionData = execution || initialData;
  const status = executionData.status;
  const created_at = executionData.created_at || executionData.start_time;
  const completed_at = executionData.completed_at || executionData.end_time;
  const { inputs, outputs, progress = {} } = executionData;

  const getStatusIcon = (nodeStatus?: string) => {
    switch (nodeStatus) {
      case 'completed':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'failed':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'running':
        return <LoadingOutlined style={{ color: '#1890ff' }} />;
      default:
        return <ClockCircleOutlined style={{ color: '#8c8c8c' }} />;
    }
  };

  const getStatusColor = (nodeStatus?: string) => {
    switch (nodeStatus) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      case 'running':
        return 'processing';
      default:
        return 'default';
    }
  };

  const completedNodes = Object.values(progress).filter((p) => p.status === 'completed').length;
  const totalNodes = Object.keys(progress).length;
  const progressPercent = totalNodes > 0 ? Math.round((completedNodes / totalNodes) * 100) : 0;

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/executions')}>
            Back to Executions
          </Button>
          <Title level={2} style={{ margin: 0 }}>
            Execution Details
          </Title>
        </Space>
        <Tag color={getStatusColor(status)} style={{ fontSize: '16px', padding: '8px 16px' }}>
          {status?.toUpperCase()}
        </Tag>
      </div>

      <Card>
        <Descriptions column={2}>
          <Descriptions.Item label="Execution ID">{id}</Descriptions.Item>
          <Descriptions.Item label="Workflow">
            {executionData.workflow_name || executionData.workflow_path}
          </Descriptions.Item>
          <Descriptions.Item label="Started">
            {new Date(created_at).toLocaleString()}
          </Descriptions.Item>
          <Descriptions.Item label="Completed">
            {completed_at ? new Date(completed_at).toLocaleString() : 'In Progress'}
          </Descriptions.Item>
        </Descriptions>

        {status === 'running' && (
          <div style={{ marginTop: 20 }}>
            <Text>
              Progress: {completedNodes} / {totalNodes} nodes completed
            </Text>
            <Progress percent={progressPercent} status="active" />
          </div>
        )}
      </Card>

      <Card title="Inputs">
        <pre style={{ margin: 0, fontSize: '12px' }}>{JSON.stringify(inputs, null, 2)}</pre>
      </Card>

      <Card title="Node Progress">
        <Collapse>
          {Object.entries(progress).map(([nodeName, nodeProgress]) => {
            // Handle both string status and full progress object
            const status = typeof nodeProgress === 'string' ? nodeProgress : nodeProgress.status;
            const isProgressObject = typeof nodeProgress === 'object' && nodeProgress !== null;

            return (
              <Panel
                key={nodeName}
                header={
                  <Space>
                    {getStatusIcon(status)}
                    <Text strong>{nodeName}</Text>
                    <Tag color={getStatusColor(status)}>{status || 'pending'}</Tag>
                  </Space>
                }
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  {isProgressObject && nodeProgress.started_at && (
                    <Text type="secondary">
                      Started: {new Date(nodeProgress.started_at).toLocaleString()}
                    </Text>
                  )}
                  {isProgressObject && nodeProgress.completed_at && (
                    <Text type="secondary">
                      Completed: {new Date(nodeProgress.completed_at).toLocaleString()}
                    </Text>
                  )}

                  {isProgressObject && nodeProgress.error && (
                    <Alert message="Error" description={nodeProgress.error} type="error" showIcon />
                  )}

                  {isProgressObject && nodeProgress.output && (
                    <div>
                      <Text strong>Output:</Text>
                      <pre style={{ margin: '8px 0', fontSize: '12px' }}>
                        {JSON.stringify(nodeProgress.output, null, 2)}
                      </pre>
                    </div>
                  )}

                  {!isProgressObject && <Text type="secondary">Status: {status}</Text>}
                </Space>
              </Panel>
            );
          })}
        </Collapse>
      </Card>

      {outputs && (
        <Card title="Final Outputs">
          <pre style={{ margin: 0, fontSize: '12px' }}>{JSON.stringify(outputs, null, 2)}</pre>
        </Card>
      )}

      {executionData.error && (
        <Alert message="Execution Error" description={executionData.error} type="error" showIcon />
      )}
    </Space>
  );
};
