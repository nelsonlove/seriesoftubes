import React, { useState } from 'react';
import { Card, List, Input, Tag, Space, Typography, Spin, Empty, Button } from 'antd';
import {
  SearchOutlined,
  FileTextOutlined,
  PlusOutlined,
  // UploadOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
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

  const handleWorkflowCreated = () => {
    // TODO: Select the newly created workflow when workflowId is implemented
    refetch();
  };

  return (
    <>
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', maxHeight: 'calc(100vh - 168px)' }}>
        <Card
          style={{
            marginBottom: '24px',
            borderRadius: '16px',
            flexShrink: 0,
          }}
        >
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                width: '100%',
              }}
            >
              <div>
                <Text strong style={{ fontSize: '16px', display: 'block' }}>
                  Manage Workflows
                </Text>
                <Text type="secondary" style={{ fontSize: '14px' }}>
                  {filteredWorkflows.length} workflow{filteredWorkflows.length !== 1 ? 's' : ''}
                </Text>
              </div>
              <Space>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => refetch()}
                  loading={isLoading}
                  size="large"
                  title="Refresh workflows"
                />
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setShowNewWorkflowModal(true)}
                  size="large"
                >
                  New Workflow
                </Button>
              </Space>
            </div>

            <Search
              placeholder="Search workflows by name, description, or inputs..."
              prefix={<SearchOutlined />}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              allowClear
              size="large"
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

        <div style={{ flex: 1, overflow: 'auto', paddingTop: 4 }}>
          <List
            dataSource={filteredWorkflows}
            renderItem={(workflow: WorkflowSummary) => (
              <Card
                hoverable
                style={{
                  marginBottom: 16,
                  borderRadius: 16,
                  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                  cursor: 'pointer',
                  border: '1px solid transparent',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.borderColor = '#4f46e5';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.borderColor = 'transparent';
                }}
                onClick={() => onSelectWorkflow(workflow.path)}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
                  {/* Workflow Icon */}
                  <div
                    style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '12px',
                      background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <FileTextOutlined
                      style={{
                        fontSize: 20,
                        color: 'white',
                      }}
                    />
                  </div>

                  {/* Workflow Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {/* Header with title and status */}
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        marginBottom: '8px',
                      }}
                    >
                      <Text
                        strong
                        style={{
                          fontSize: '16px',
                          fontWeight: '600',
                          lineHeight: '1.5',
                        }}
                      >
                        {workflow.name}
                      </Text>
                      <div
                        style={{ display: 'flex', gap: '6px', flexShrink: 0, marginLeft: '12px' }}
                      >
                        {/* Visibility badge */}
                        <Tag
                          color={workflow.is_public ? 'green' : 'default'}
                          style={{
                            borderRadius: '12px',
                            fontSize: '11px',
                            fontWeight: '500',
                            padding: '2px 8px',
                            border: 'none',
                          }}
                        >
                          {workflow.is_public ? 'Public' : 'Private'}
                        </Tag>

                        {/* Complexity indicator */}
                        <Tag
                          color="blue"
                          style={{
                            borderRadius: '12px',
                            fontSize: '11px',
                            fontWeight: '500',
                            padding: '2px 8px',
                            border: 'none',
                          }}
                        >
                          {Object.keys(workflow.inputs).length} input
                          {Object.keys(workflow.inputs).length !== 1 ? 's' : ''}
                        </Tag>
                      </div>
                    </div>

                    {/* Description */}
                    {workflow.description && (
                      <Text
                        type="secondary"
                        style={{
                          fontSize: '14px',
                          lineHeight: '1.5',
                          display: '-webkit-box',
                          marginBottom: '12px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                        }}
                      >
                        {workflow.description}
                      </Text>
                    )}

                    {/* Metadata */}
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginTop: '12px',
                      }}
                    >
                      <Space size="small">
                        <Text type="secondary" style={{ fontSize: '12px', fontWeight: '500' }}>
                          v{workflow.version}
                        </Text>
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          •
                        </Text>
                        <Text type="secondary" style={{ fontSize: '12px', fontWeight: '500' }}>
                          {workflow.username}
                        </Text>
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          •
                        </Text>
                        <Text type="secondary" style={{ fontSize: '12px', fontWeight: '500' }}>
                          {new Date(workflow.updated_at).toLocaleDateString()}
                        </Text>
                      </Space>

                      {/* Quick action hint */}
                      <Text
                        type="secondary"
                        style={{
                          fontSize: '11px',
                          fontWeight: '500',
                          textTransform: 'uppercase',
                          letterSpacing: '0.05em',
                          opacity: 0.6,
                        }}
                      >
                        Click to view
                      </Text>
                    </div>

                    {/* Input tags */}
                    {Object.keys(workflow.inputs).length > 0 && (
                      <div style={{ marginTop: '12px' }}>
                        <Space wrap size="small">
                          {Object.keys(workflow.inputs)
                            .slice(0, 4)
                            .map((input) => (
                              <Tag
                                key={input}
                                style={{
                                  fontSize: '11px',
                                  borderRadius: '6px',
                                  padding: '2px 6px',
                                  backgroundColor: '#f1f5f9',
                                  border: '1px solid #e2e8f0',
                                  color: '#475569',
                                }}
                              >
                                {input}
                              </Tag>
                            ))}
                          {Object.keys(workflow.inputs).length > 4 && (
                            <Tag
                              style={{
                                fontSize: '11px',
                                borderRadius: '6px',
                                padding: '2px 6px',
                                backgroundColor: '#f1f5f9',
                                border: '1px solid #e2e8f0',
                                color: '#475569',
                              }}
                            >
                              +{Object.keys(workflow.inputs).length - 4} more
                            </Tag>
                          )}
                        </Space>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            )}
          />
        </div>
      </div>

      <NewWorkflowModal
        visible={showNewWorkflowModal}
        onClose={() => setShowNewWorkflowModal(false)}
        onSuccess={handleWorkflowCreated}
      />
    </>
  );
};
