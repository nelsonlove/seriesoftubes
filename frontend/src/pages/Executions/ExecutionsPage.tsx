import React from 'react';
import { Typography, Table, Tag, Button } from 'antd';
import { ReloadOutlined, EyeOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { executionAPI } from '../../api/client';
import type { ExecutionResponse } from '../../types/workflow';

const { Title } = Typography;

export const ExecutionsPage: React.FC = () => {
  const navigate = useNavigate();

  const {
    data: executions,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['executions'],
    queryFn: () => executionAPI.list(),
    refetchInterval: 5000, // Auto-refresh every 5 seconds
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'green'; // Match the detail view
      case 'failed':
        return 'red'; // Match the detail view
      case 'running':
        return 'blue'; // Match the detail view
      default:
        return 'default';
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 300,
      ellipsis: true,
      render: (id: string | undefined, record: ExecutionResponse) => {
        return id || record.execution_id || 'N/A';
      },
    },
    {
      title: 'Workflow',
      key: 'workflow',
      render: (_: any, record: ExecutionResponse) => {
        const path = record.workflow_path;
        if (!path) {
          return record.workflow_name || 'Unknown';
        }
        const name = path.split('/').pop()?.replace('.yaml', '') || path;
        return name;
      },
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        if (!status) return <Tag>UNKNOWN</Tag>;
        return <Tag color={getStatusColor(status)}>{status.toUpperCase()}</Tag>;
      },
    },
    {
      title: 'Started',
      key: 'started',
      render: (_: any, record: ExecutionResponse) => {
        const date = record.created_at || record.start_time;
        return date ? new Date(date).toLocaleString() : 'N/A';
      },
    },
    {
      title: 'Duration',
      key: 'duration',
      render: (_: any, record: ExecutionResponse) => {
        const endTime = record.completed_at || record.end_time;
        const startTime = record.created_at || record.start_time;
        
        // If no start time, can't calculate duration
        if (!startTime) return 'N/A';
        
        // For running/pending workflows without end time
        if (!endTime && (record.status === 'running' || record.status === 'pending')) {
          return 'In Progress';
        }
        
        // For completed/failed workflows, use current time if no end time
        const start = new Date(startTime).getTime();
        const end = endTime ? new Date(endTime).getTime() : Date.now();
        const duration = Math.round((end - start) / 1000);
        
        // Format duration nicely
        if (duration < 60) {
          return `${duration}s`;
        } else if (duration < 3600) {
          const minutes = Math.floor(duration / 60);
          const seconds = duration % 60;
          return `${minutes}m ${seconds}s`;
        } else {
          const hours = Math.floor(duration / 3600);
          const minutes = Math.floor((duration % 3600) / 60);
          return `${hours}h ${minutes}m`;
        }
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: ExecutionResponse) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/executions/${record.id || record.execution_id}`)}
        >
          View
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <Title level={2}>Executions</Title>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
          Refresh
        </Button>
      </div>

      <Table
        dataSource={executions}
        columns={columns}
        loading={isLoading}
        rowKey={(record) => record.id || record.execution_id || 'unknown'}
        pagination={{ pageSize: 20 }}
      />
    </div>
  );
};
