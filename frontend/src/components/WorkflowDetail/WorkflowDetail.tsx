import React from 'react';
import { Card, Spin, Typography, Space, Tag, Descriptions, Button } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { workflowAPI } from '../../api/client';

const { Title, Text } = Typography;

interface WorkflowDetailProps {
  path: string;
}

export const WorkflowDetail: React.FC<WorkflowDetailProps> = ({ path }) => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['workflow', path],
    queryFn: () => workflowAPI.get(path),
    enabled: !!path,
  });

  if (isLoading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <Spin size="large" />
        </div>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <Text type="danger">Failed to load workflow details</Text>
      </Card>
    );
  }

  const { workflow } = data;

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Title level={3}>{workflow.name}</Title>
            <Button type="primary" icon={<PlayCircleOutlined />}>
              Run Workflow
            </Button>
          </div>

          <Descriptions column={1}>
            <Descriptions.Item label="Path">{data.path}</Descriptions.Item>
            <Descriptions.Item label="Version">{workflow.version}</Descriptions.Item>
            <Descriptions.Item label="Description">
              {workflow.description || 'No description available'}
            </Descriptions.Item>
            <Descriptions.Item label="Total Nodes">
              {Object.keys(workflow.nodes).length}
            </Descriptions.Item>
            <Descriptions.Item label="Inputs">
              {Object.keys(workflow.inputs).length}
            </Descriptions.Item>
            <Descriptions.Item label="Outputs">
              {Object.keys(workflow.outputs).length}
            </Descriptions.Item>
          </Descriptions>
        </Space>
      </Card>

      <Card title="Inputs">
        <Space direction="vertical" style={{ width: '100%' }}>
          {Object.entries(workflow.inputs).map(([name, input]) => (
            <div key={name}>
              <Space>
                <Text strong>{name}</Text>
                <Tag color="blue">{input.type}</Tag>
                {input.required && <Tag color="red">Required</Tag>}
              </Space>
              {input.description && (
                <Text type="secondary" style={{ display: 'block', marginLeft: 20 }}>
                  {input.description}
                </Text>
              )}
            </div>
          ))}
        </Space>
      </Card>

      <Card title="Nodes">
        <Space direction="vertical" style={{ width: '100%' }}>
          {Object.entries(workflow.nodes).map(([name, node]) => (
            <Card key={name} size="small">
              <Space>
                <Text strong>{name}</Text>
                <Tag color="purple">{node.type}</Tag>
                {node.depends_on && node.depends_on.length > 0 && (
                  <Text type="secondary">Depends on: {node.depends_on.join(', ')}</Text>
                )}
              </Space>
            </Card>
          ))}
        </Space>
      </Card>

      <Card title="Outputs">
        <Space direction="vertical">
          {Object.entries(workflow.outputs).map(([name, nodeRef]) => (
            <div key={name}>
              <Text strong>{name}</Text> → <Tag>{nodeRef}</Tag>
            </div>
          ))}
        </Space>
      </Card>
    </Space>
  );
};
