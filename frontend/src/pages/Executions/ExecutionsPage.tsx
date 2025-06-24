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
        return 'success';
      case 'failed':
        return 'error';
      case 'running':
        return 'processing';
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
        if (!endTime || !startTime) return 'In Progress';
        const start = new Date(startTime).getTime();
        const end = new Date(endTime).getTime();
        const duration = Math.round((end - start) / 1000);
        return `${duration}s`;
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
