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
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  FileOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { executionAPI, workflowAPI } from '../../api/client';
import { useExecutionStore } from '../../stores/execution';
import api from '../../api/client';
import { useThemeStore } from '../../stores/theme';
import type { ExecutionProgress } from '../../types/workflow';

const { Title, Text } = Typography;
// Removed Panel import - using items prop instead

export const ExecutionDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [, setEventSource] = useState<EventSource | null>(null);
  const { mode: themeMode } = useThemeStore();

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

  // Fetch workflow definition to get all nodes
  const { data: workflowData, isLoading: workflowLoading } = useQuery({
    queryKey: ['workflow', initialData?.workflow_id],
    queryFn: () => workflowAPI.get(initialData!.workflow_id),
    enabled: !!initialData?.workflow_id,
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
    if (!id) return;

    // Use initial data if execution is not yet in store
    const currentExecution = execution || initialData;
    if (!currentExecution) return;

    // Only set up SSE for running executions
    if (currentExecution.status !== 'running' && currentExecution.status !== 'pending') {
      return;
    }

    const es = executionAPI.stream(id, (data: any) => {
      console.log('SSE data received:', data);

      // Update execution with latest data from SSE
      if (
        data.type &&
        (data.type === 'status' || data.type === 'update' || data.type === 'complete')
      ) {
        const updatedExecution = {
          ...currentExecution,
          status: data.status || currentExecution.status,
          started_at: data.started_at || currentExecution.started_at,
          completed_at: data.completed_at || currentExecution.completed_at,
          outputs: data.outputs || currentExecution.outputs,
          errors: data.errors || currentExecution.errors,
          progress: data.progress || currentExecution.progress || {},
        };
        setExecution(updatedExecution);
        
        // If execution is complete, close the SSE connection
        if (data.status === 'completed' || data.status === 'failed') {
          es.close();
        }
      }

      // Update progress for each node (if progress data is available)
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
  }, [id, execution, initialData, updateProgress, setExecution]);

  if (isLoading || workflowLoading) {
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
  const created_at =
    executionData.created_at || executionData.start_time || executionData.started_at;
  const completed_at = executionData.completed_at || executionData.end_time;
  const { inputs, outputs, progress = {} } = executionData;

  // Get all nodes from workflow definition, or fall back to progress keys
  const allNodeNames = workflowData?.parsed?.nodes
    ? Object.keys(workflowData.parsed.nodes)
    : Object.keys(progress);

  // Helper function to safely format dates
  const formatDate = (dateStr: string | null | undefined): string => {
    if (!dateStr) return 'In Progress';
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return 'Invalid Date';
      return date.toLocaleString();
    } catch {
      return 'Invalid Date';
    }
  };

  const getStatusIcon = (nodeStatus?: string) => {
    switch (nodeStatus) {
      case 'completed':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'failed':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'running':
        return <LoadingOutlined style={{ color: '#1890ff' }} />;
      case 'skipped':
        return <CloseCircleOutlined style={{ color: '#d9d9d9' }} />;
      default:
        return <ClockCircleOutlined style={{ color: '#8c8c8c' }} />;
    }
  };

  const getStatusColor = (nodeStatus?: string) => {
    switch (nodeStatus) {
      case 'completed':
        return 'green'; // Use lighter green instead of 'success'
      case 'failed':
        return 'red';
      case 'running':
        return 'blue';
      case 'skipped':
        return 'default';
      default:
        return 'default';
    }
  };

  // Calculate progress using all nodes from workflow definition
  const completedNodes = allNodeNames.filter((nodeName) => {
    const nodeProgress = progress[nodeName];
    const status = typeof nodeProgress === 'string' ? nodeProgress : nodeProgress?.status;
    return status === 'completed';
  }).length;

  const totalNodes = allNodeNames.length;

  // Calculate progress percentage and text
  const progressPercent = totalNodes > 0 ? Math.round((completedNodes / totalNodes) * 100) : 0;
  const progressText =
    totalNodes > 0
      ? `${completedNodes} / ${totalNodes} nodes completed`
      : 'Workflow progress not available yet';

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
          <Descriptions.Item label="Started">{formatDate(created_at)}</Descriptions.Item>
          <Descriptions.Item label="Completed">{formatDate(completed_at)}</Descriptions.Item>
        </Descriptions>

        {status === 'running' && (
          <div style={{ marginTop: 20 }}>
            <Text>Progress: {progressText}</Text>
            {totalNodes > 0 && <Progress percent={progressPercent} status="active" />}
          </div>
        )}
      </Card>

      <Card title="Inputs">
        <pre 
          style={{ 
            margin: 0, 
            fontSize: '12px',
            background: themeMode === 'dark' ? '#1e293b' : '#f5f5f5',
            color: themeMode === 'dark' ? '#f1f5f9' : '#0f172a',
            padding: '12px',
            borderRadius: '4px',
            border: `1px solid ${themeMode === 'dark' ? '#475569' : '#d9d9d9'}`,
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
            overflowWrap: 'break-word',
          }}
        >
          {JSON.stringify(inputs, null, 2)}
        </pre>
      </Card>

      <Card title="Node Progress">
        <Collapse
          expandIconPosition="start"
          items={allNodeNames.map((nodeName) => {
            const nodeProgress = progress[nodeName];
            // Handle both string status and full progress object
            let status: string;
            if (nodeProgress) {
              status = typeof nodeProgress === 'string' ? nodeProgress : nodeProgress.status;
            } else {
              // If no progress data for this node, determine status based on execution state
              if (executionData.status === 'failed' || executionData.status === 'cancelled') {
                status = 'skipped'; // Nodes that never ran due to execution failure
              } else {
                status = 'pending'; // Nodes that haven't started yet in running execution
              }
            }
            const isProgressObject = typeof nodeProgress === 'object' && nodeProgress !== null;

            // Determine if this node should be expandable
            const hasContent = status === 'completed' || status === 'failed';

            return {
              key: nodeName,
              label: (
                <Space>
                  {getStatusIcon(status)}
                  <Text strong style={{ color: status === 'skipped' ? '#8c8c8c' : undefined }}>
                    {nodeName}
                  </Text>
                  {status !== 'skipped' && (
                    <Tag color={getStatusColor(status)}>{status || 'pending'}</Tag>
                  )}
                </Space>
              ),
              children: hasContent ? (
                <Space direction="vertical" style={{ width: '100%' }}>
                  {/* Show actual output for completed nodes */}
                  {status === 'completed' && (
                    <div>
                      {outputs && outputs[nodeName] ? (
                        <div>
                          <Text strong>Output:</Text>
                          <pre
                            style={{
                              margin: '8px 0',
                              fontSize: '12px',
                              background: themeMode === 'dark' ? '#1e293b' : '#f5f5f5',
                              color: themeMode === 'dark' ? '#f1f5f9' : '#0f172a',
                              padding: '8px',
                              borderRadius: '4px',
                              border: `1px solid ${themeMode === 'dark' ? '#475569' : '#d9d9d9'}`,
                              whiteSpace: 'pre-wrap',
                              wordWrap: 'break-word',
                              overflowWrap: 'break-word',
                              maxWidth: '100%',
                              overflow: 'hidden',
                            }}
                          >
                            {JSON.stringify(outputs[nodeName], null, 2)}
                          </pre>
                        </div>
                      ) : (
                        <Text type="secondary">No output data available</Text>
                      )}
                    </div>
                  )}

                  {/* Show error details directly for failed nodes */}
                  {status === 'failed' && (
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <div
                        style={{
                          padding: '8px',
                          background: themeMode === 'dark' ? '#431417' : '#fff2f0',
                          border: `1px solid ${themeMode === 'dark' ? '#7f1d1d' : '#ffccc7'}`,
                          borderRadius: '4px',
                          fontFamily: 'monospace',
                          fontSize: '12px',
                          color: themeMode === 'dark' ? '#fca5a5' : '#a8071a',
                        }}
                      >
                        {/* Try to get error from new progress format first, then fall back to old errors format */}
                        {isProgressObject && nodeProgress.error
                          ? nodeProgress.error
                          : executionData.errors && executionData.errors[nodeName]
                            ? executionData.errors[nodeName]
                            : 'Node execution failed (no error details available)'}
                      </div>
                      
                      {/* Show detailed error information if available */}
                      {executionData.error_details && executionData.error_details[nodeName] && (
                        <div>
                          <Text strong style={{ display: 'block', marginBottom: '4px' }}>Node Inputs:</Text>
                          <pre
                            style={{
                              margin: '0',
                              fontSize: '11px',
                              background: themeMode === 'dark' ? '#1e293b' : '#f5f5f5',
                              color: themeMode === 'dark' ? '#f1f5f9' : '#0f172a',
                              padding: '8px',
                              borderRadius: '4px',
                              border: `1px solid ${themeMode === 'dark' ? '#475569' : '#d9d9d9'}`,
                              whiteSpace: 'pre-wrap',
                              wordWrap: 'break-word',
                              overflowWrap: 'break-word',
                              maxWidth: '100%',
                              overflow: 'hidden',
                            }}
                          >
                            {JSON.stringify(executionData.error_details[nodeName].inputs, null, 2)}
                          </pre>
                        </div>
                      )}
                    </Space>
                  )}

                  {/* Detailed progress object (if available) */}
                  {isProgressObject && nodeProgress.started_at && (
                    <Text type="secondary">Started: {formatDate(nodeProgress.started_at)}</Text>
                  )}
                  {isProgressObject && nodeProgress.completed_at && (
                    <Text type="secondary">Completed: {formatDate(nodeProgress.completed_at)}</Text>
                  )}

                  {isProgressObject && nodeProgress.error && (
                    <div
                      style={{
                        padding: '8px',
                        background: themeMode === 'dark' ? '#431417' : '#fff2f0',
                        border: `1px solid ${themeMode === 'dark' ? '#7f1d1d' : '#ffccc7'}`,
                        borderRadius: '4px',
                        fontFamily: 'monospace',
                        fontSize: '12px',
                        color: themeMode === 'dark' ? '#fca5a5' : '#a8071a',
                      }}
                    >
                      {nodeProgress.error}
                    </div>
                  )}

                  {isProgressObject && nodeProgress.output && (
                    <div>
                      <Text strong>Output:</Text>
                      <pre
                        style={{
                          margin: '8px 0',
                          fontSize: '12px',
                          background: themeMode === 'dark' ? '#1e293b' : '#f5f5f5',
                          color: themeMode === 'dark' ? '#f1f5f9' : '#0f172a',
                          padding: '8px',
                          borderRadius: '4px',
                          border: `1px solid ${themeMode === 'dark' ? '#475569' : '#d9d9d9'}`,
                          whiteSpace: 'pre-wrap',
                          wordWrap: 'break-word',
                          overflowWrap: 'break-word',
                        }}
                      >
                        {JSON.stringify(nodeProgress.output, null, 2)}
                      </pre>
                    </div>
                  )}
                </Space>
              ) : null,
              // Disable expansion for running/pending nodes
              collapsible: hasContent ? 'header' : 'disabled',
              showArrow: hasContent,
            };
          })}
        />
      </Card>

      {outputs && (
        <Card title="Final Outputs">
          <pre
            style={{
              margin: 0,
              fontSize: '12px',
              background: themeMode === 'dark' ? '#1e293b' : '#f5f5f5',
              color: themeMode === 'dark' ? '#f1f5f9' : '#0f172a',
              padding: '12px',
              borderRadius: '4px',
              border: `1px solid ${themeMode === 'dark' ? '#475569' : '#d9d9d9'}`,
              whiteSpace: 'pre-wrap',
              wordWrap: 'break-word',
              overflowWrap: 'break-word',
            }}
          >
            {JSON.stringify(outputs, null, 2)}
          </pre>
        </Card>
      )}

      {executionData.storage_keys && Object.keys(executionData.storage_keys).length > 0 && (
        <Card title="Output Files">
          <Space direction="vertical" style={{ width: '100%' }}>
            {Object.entries(executionData.storage_keys).map(([key, storageKey]) => (
              <div key={key} style={{ 
                padding: '8px 12px',
                background: themeMode === 'dark' ? '#1e293b' : '#f5f5f5',
                borderRadius: '4px',
                border: `1px solid ${themeMode === 'dark' ? '#475569' : '#e2e8f0'}`,
              }}>
                <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                  <Space>
                    <FileOutlined />
                    <Text strong>{key === '__metadata__' ? 'Execution Metadata' : key}</Text>
                  </Space>
                  <Button
                    size="small"
                    icon={<DownloadOutlined />}
                    onClick={async () => {
                      try {
                        // Download file directly through API
                        const response = await api.get(
                          `/api/files/download-by-key?key=${encodeURIComponent(storageKey as string)}`,
                          { responseType: 'blob' }
                        );
                        
                        // Create blob URL and trigger download
                        const blob = new Blob([response.data]);
                        const url = window.URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = key === '__metadata__' ? 'metadata.json' : `${key}.json`;
                        document.body.appendChild(link);
                        link.click();
                        link.remove();
                        window.URL.revokeObjectURL(url);
                        
                        message.success('File downloaded successfully');
                      } catch (error) {
                        console.error('Download error:', error);
                        message.error('Failed to download file');
                      }
                    }}
                  >
                    Download
                  </Button>
                </Space>
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  {storageKey}
                </Text>
              </div>
            ))}
          </Space>
        </Card>
      )}

      {executionData.error && (
        <Alert message="Execution Error" description={executionData.error} type="error" showIcon />
      )}
    </Space>
  );
};
