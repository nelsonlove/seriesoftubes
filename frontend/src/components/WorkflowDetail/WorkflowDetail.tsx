import React, { useState } from 'react';
import { Card, Spin, Typography, Space, Tag, Descriptions, Button, Tabs } from 'antd';
import {
  PlayCircleOutlined,
  EditOutlined,
  InfoCircleOutlined,
  BranchesOutlined,
  CodeOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { workflowAPI } from '../../api/client';
import { RunWorkflowModal } from '../RunWorkflowModal';
import { YamlEditorModal } from '../YamlEditor';
import { DAGVisualization } from '../DAGVisualization';

const { Title, Text } = Typography;

interface WorkflowDetailProps {
  path: string;
}

export const WorkflowDetail: React.FC<WorkflowDetailProps> = ({ path }) => {
  const [showRunModal, setShowRunModal] = useState(false);
  const [showYamlEditor, setShowYamlEditor] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const { data, isLoading, error, refetch } = useQuery({
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

  // The API returns the parsed workflow structure directly in 'parsed' field
  const workflow = data.parsed || data.workflow;

  if (!workflow || workflow.error) {
    return (
      <Card>
        <Text type="warning">{workflow?.error || 'No workflow data available'}</Text>
      </Card>
    );
  }

  const tabItems = [
    {
      key: 'overview',
      label: (
        <span>
          <InfoCircleOutlined /> Overview
        </span>
      ),
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Descriptions column={2}>
            <Descriptions.Item label="Path">{data.path || data.id}</Descriptions.Item>
            <Descriptions.Item label="Version">{workflow.version}</Descriptions.Item>
            <Descriptions.Item label="Description" span={2}>
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

          <Card title="Inputs" size="small">
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

          <Card title="Outputs" size="small">
            <Space direction="vertical">
              {Object.entries(workflow.outputs).map(([name, nodeRef]) => (
                <div key={name}>
                  <Text strong>{name}</Text> → <Tag>{nodeRef}</Tag>
                </div>
              ))}
            </Space>
          </Card>
        </Space>
      ),
    },
    {
      key: 'dag',
      label: (
        <span>
          <BranchesOutlined /> DAG View
        </span>
      ),
      children: (
        <Card>
          <DAGVisualization
            nodes={workflow.nodes}
            outputs={workflow.outputs}
            inputs={workflow.inputs}
          />
        </Card>
      ),
    },
    {
      key: 'nodes',
      label: (
        <span>
          <CodeOutlined /> Node Details
        </span>
      ),
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size="medium">
          {Object.entries(workflow.nodes).map(([name, node]) => (
            <Card key={name} size="small">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space>
                  <Text strong>{name}</Text>
                  <Tag color="purple">{node.type}</Tag>
                  {node.depends_on && node.depends_on.length > 0 && (
                    <Text type="secondary">Depends on: {node.depends_on.join(', ')}</Text>
                  )}
                </Space>
                {node.description && (
                  <Text type="secondary" style={{ marginTop: 4 }}>
                    {node.description}
                  </Text>
                )}
                <pre
                  style={{
                    background: '#f5f5f5',
                    padding: 8,
                    borderRadius: 4,
                    fontSize: 12,
                    overflow: 'auto',
                  }}
                >
                  {JSON.stringify(node.config, null, 2)}
                </pre>
              </Space>
            </Card>
          ))}
        </Space>
      ),
    },
    {
      key: 'history',
      label: (
        <span>
          <HistoryOutlined /> Execution History
        </span>
      ),
      children: (
        <Card>
          <Text type="secondary">Execution history will be displayed here</Text>
        </Card>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 16,
          }}
        >
          <Title level={3} style={{ margin: 0 }}>
            {workflow.name}
          </Title>
          <Space>
            <Button icon={<EditOutlined />} onClick={() => setShowYamlEditor(true)}>
              Edit YAML
            </Button>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => setShowRunModal(true)}
            >
              Run Workflow
            </Button>
          </Space>
        </div>

        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
      </Card>

      <RunWorkflowModal
        workflow={{ ...data, workflow: workflow, path: data.path || data.id }}
        open={showRunModal}
        onClose={() => setShowRunModal(false)}
      />

      <YamlEditorModal
        workflowPath={path}
        open={showYamlEditor}
        onClose={() => setShowYamlEditor(false)}
        onSave={() => refetch()}
      />
    </Space>
  );
};
