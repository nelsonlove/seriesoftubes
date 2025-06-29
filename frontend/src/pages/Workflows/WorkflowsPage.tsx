import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Typography } from 'antd';
import { AppstoreOutlined } from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';
import { WorkflowList } from '../../components/WorkflowList';
import { WorkflowDetail } from '../../components/WorkflowDetail';

const { Title } = Typography;

export const WorkflowsPage: React.FC = () => {
  const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null);
  const [searchParams] = useSearchParams();
  const searchQuery = searchParams.get('search') || '';

  return (
    <div style={{ height: 'calc(100vh - 232px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: '32px', flexShrink: 0 }}>
        <Title
          level={1}
          style={{
            margin: 0,
            fontSize: '32px',
            fontWeight: '700',
            letterSpacing: '-0.025em',
          }}
        >
          Workflows
        </Title>
        <Typography.Text
          type="secondary"
          style={{
            fontSize: '16px',
            marginTop: '8px',
            display: 'block',
          }}
        >
          Create, manage, and execute your workflow automations
        </Typography.Text>
      </div>

      <Row gutter={32} style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Col span={10}>
          <WorkflowList onSelectWorkflow={setSelectedWorkflow} searchQuery={searchQuery} />
        </Col>
        <Col span={14} style={{ height: '100%' }}>
          {selectedWorkflow ? (
            <WorkflowDetail path={selectedWorkflow} />
          ) : (
            <Card
              style={{
                height: '100%',
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'center',
                textAlign: 'center',
                border: '2px dashed #e2e8f0',
                background: 'transparent',
                paddingTop: '80px',
              }}
            >
              <div>
                <div
                  style={{
                    width: '64px',
                    height: '64px',
                    background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                    borderRadius: '16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 24px',
                    opacity: 0.1,
                  }}
                >
                  <AppstoreOutlined style={{ fontSize: '24px', color: 'white' }} />
                </div>
                <Title level={3} style={{ color: '#94a3b8', fontWeight: '600' }}>
                  Select a workflow
                </Title>
                <Typography.Text type="secondary" style={{ fontSize: '16px' }}>
                  Choose a workflow from the list to view its details, edit configuration, or run
                  executions
                </Typography.Text>
              </div>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
};
