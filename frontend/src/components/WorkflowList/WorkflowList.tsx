import React, { useState } from 'react';
import { Card, List, Input, Tag, Space, Typography, Spin, Empty, Button } from 'antd';
import { SearchOutlined, FileTextOutlined, PlusOutlined, UploadOutlined, ReloadOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { workflowAPI } from '../../api/client';
import { NewWorkflowModal } from '../NewWorkflowModal';
import type { WorkflowSummary } from '../../types/workflow';

const { Search } = Input;
const { Text } = Typography;

interface WorkflowListProps {
  onSelectWorkflow: (path: string) => void;
}

export const WorkflowList: React.FC<WorkflowListProps> = ({ onSelectWorkflow }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTag, setSelectedTag] = useState<string | undefined>();
  const [showNewWorkflowModal, setShowNewWorkflowModal] = useState(false);

  const {
    data: workflows,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['workflows'], // Remove search/tag from key to prevent refetching
    queryFn: () => workflowAPI.list({}), // Fetch all workflows once
  });

  // Filter workflows based on search term
  const filteredWorkflows = React.useMemo(() => {
    if (!workflows) return [];

    return workflows.filter((workflow) => {
      // Search filter
      if (searchTerm) {
        const searchLower = searchTerm.toLowerCase();
        const matchesName = workflow.name.toLowerCase().includes(searchLower);
        const matchesDescription =
          workflow.description?.toLowerCase().includes(searchLower) || false;
        const matchesPath = workflow.path.toLowerCase().includes(searchLower);
        const matchesInputs = Object.keys(workflow.inputs).some((input) =>
          input.toLowerCase().includes(searchLower)
        );

        if (!matchesName && !matchesDescription && !matchesPath && !matchesInputs) {
          return false;
        }
      }

      // Tag filter would go here when implemented
      if (selectedTag) {
        // return workflow.tags?.includes(selectedTag) || false;
      }

      return true;
    });
  }, [workflows, searchTerm, selectedTag]);

  // Tags feature not implemented in backend yet
  const allTags: string[] = [];

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return <Empty description={`Failed to load workflows: ${error.message}`} />;
  }

  const handleWorkflowCreated = (workflowId: string) => {
    // TODO: Select the newly created workflow
    refetch();
  };

  return (
    <>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Card>
          <Space direction="vertical" style={{ width: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setShowNewWorkflowModal(true)}
              >
                New Workflow
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => refetch()}
                loading={isLoading}
              >
                Refresh
              </Button>
            </div>

            <Search
              placeholder="Search workflows..."
              prefix={<SearchOutlined />}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              allowClear
            />

            {allTags.length > 0 && (
            <Space wrap>
              <Text>Filter by tag:</Text>
              <Tag
                color={!selectedTag ? 'blue' : 'default'}
                style={{ cursor: 'pointer' }}
                onClick={() => setSelectedTag(undefined)}
              >
                All
              </Tag>
              {allTags.map((tag) => (
                <Tag
                  key={tag}
                  color={selectedTag === tag ? 'blue' : 'default'}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelectedTag(tag)}
                >
                  {tag}
                </Tag>
              ))}
            </Space>
          )}
        </Space>
      </Card>

      <List
        dataSource={filteredWorkflows}
        renderItem={(workflow: WorkflowSummary) => (
          <Card
            hoverable
            style={{ marginBottom: 16 }}
            onClick={() => onSelectWorkflow(workflow.path)}
          >
            <Card.Meta
              avatar={<FileTextOutlined style={{ fontSize: 24 }} />}
              title={
                <Space>
                  {workflow.name}
                  {workflow.is_public ? (
                    <Tag color="green">Public</Tag>
                  ) : (
                    <Tag>Private</Tag>
                  )}
                </Space>
              }
              description={
                <Space direction="vertical" style={{ width: '100%' }}>
                  {workflow.description && <Text>{workflow.description}</Text>}
                  <Space>
                    <Text type="secondary">v{workflow.version}</Text>
                    <Text type="secondary">•</Text>
                    <Text type="secondary">by {workflow.username}</Text>
                    <Text type="secondary">•</Text>
                    <Text type="secondary">{new Date(workflow.updated_at).toLocaleDateString()}</Text>
                  </Space>
                </Space>
              }
            />
          </Card>
        )}
      />
    </Space>

      <NewWorkflowModal
        visible={showNewWorkflowModal}
        onClose={() => setShowNewWorkflowModal(false)}
        onSuccess={handleWorkflowCreated}
      />
    </>
  );
};
