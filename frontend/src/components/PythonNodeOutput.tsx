import React, { useEffect, useState, useRef } from 'react';
import { Typography, Space, Tabs, Alert, Badge } from 'antd';
import { CodeOutlined, WarningOutlined } from '@ant-design/icons';
import { executionAPI } from '../api/client';
import { useThemeStore } from '../stores/theme';

const { Text } = Typography;

interface PythonNodeOutputProps {
  executionId: string;
  nodeName: string;
  nodeStatus: string;
  initialOutput?: {
    stdout?: string;
    stderr?: string;
  };
}

export const PythonNodeOutput: React.FC<PythonNodeOutputProps> = ({
  executionId,
  nodeName,
  nodeStatus,
  initialOutput,
}) => {
  const { mode: themeMode } = useThemeStore();
  const [stdout, setStdout] = useState(initialOutput?.stdout || '');
  const [stderr, setStderr] = useState(initialOutput?.stderr || '');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const stdoutEndRef = useRef<HTMLDivElement>(null);
  const stderrEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Only stream if node is running
    if (nodeStatus !== 'running') {
      return;
    }

    setIsStreaming(true);
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const url = `${apiUrl}/api/executions/${executionId}/stream/${nodeName}`;
    
    // Get auth token
    const token = localStorage.getItem('token');
    if (!token) {
      setError('No authentication token');
      return;
    }

    // Create EventSource with auth header workaround
    const es = new EventSource(url + `?token=${encodeURIComponent(token)}`);
    eventSourceRef.current = es;

    es.onopen = () => {
      console.log(`Streaming output for node ${nodeName}`);
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case 'initial':
            if (data.output) {
              setStdout(data.output.stdout || '');
              setStderr(data.output.stderr || '');
            }
            break;
            
          case 'stdout':
            setStdout((prev) => prev + data.text);
            // Auto-scroll to bottom
            setTimeout(() => stdoutEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
            break;
            
          case 'stderr':
            setStderr((prev) => prev + data.text);
            // Auto-scroll to bottom
            setTimeout(() => stderrEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
            break;
            
          case 'complete':
            setIsStreaming(false);
            if (data.final_output) {
              setStdout(data.final_output.stdout || stdout);
              setStderr(data.final_output.stderr || stderr);
            }
            es.close();
            break;
            
          case 'error':
            setError(data.message);
            setIsStreaming(false);
            es.close();
            break;
            
          case 'timeout':
            setError('Streaming timeout reached');
            setIsStreaming(false);
            es.close();
            break;
        }
      } catch (err) {
        console.error('Error parsing SSE data:', err);
      }
    };

    es.onerror = (err) => {
      console.error('SSE error:', err);
      setError('Connection lost');
      setIsStreaming(false);
      es.close();
    };

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [executionId, nodeName, nodeStatus]);

  const outputStyle: React.CSSProperties = {
    fontFamily: 'monospace',
    fontSize: '12px',
    background: themeMode === 'dark' ? '#1e293b' : '#f5f5f5',
    color: themeMode === 'dark' ? '#f1f5f9' : '#0f172a',
    padding: '12px',
    borderRadius: '4px',
    border: `1px solid ${themeMode === 'dark' ? '#475569' : '#d9d9d9'}`,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
    overflowY: 'auto',
    maxHeight: '400px',
    minHeight: '100px',
  };

  const tabItems = [
    {
      key: 'stdout',
      label: (
        <Space>
          <CodeOutlined />
          Output
          {stdout && <Badge count={stdout.split('\n').length - 1} showZero />}
        </Space>
      ),
      children: (
        <div style={outputStyle}>
          {stdout || <Text type="secondary">No output yet...</Text>}
          <div ref={stdoutEndRef} />
        </div>
      ),
    },
    {
      key: 'stderr',
      label: (
        <Space>
          <WarningOutlined />
          Errors
          {stderr && <Badge count={stderr.split('\n').length - 1} showZero color="red" />}
        </Space>
      ),
      children: (
        <div style={{ ...outputStyle, color: themeMode === 'dark' ? '#fca5a5' : '#a8071a' }}>
          {stderr || <Text type="secondary">No errors</Text>}
          <div ref={stderrEndRef} />
        </div>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      {error && (
        <Alert
          message="Streaming Error"
          description={error}
          type="error"
          showIcon
          closable
        />
      )}
      
      {isStreaming && (
        <Alert
          message="Streaming output..."
          type="info"
          showIcon
          icon={<CodeOutlined spin />}
        />
      )}
      
      <Tabs
        defaultActiveKey="stdout"
        items={tabItems}
        size="small"
      />
    </Space>
  );
};