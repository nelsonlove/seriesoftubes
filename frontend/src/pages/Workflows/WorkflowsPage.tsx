import React, { useState } from 'react';
import { Row, Col, Card, Typography } from 'antd';
import { WorkflowList } from '../../components/WorkflowList';
import { WorkflowDetail } from '../../components/WorkflowDetail';

const { Title } = Typography;

export const WorkflowsPage: React.FC = () => {
  const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null);

  return (
    <div>
      <Title level={2}>Workflows</Title>
      <Row gutter={24}>
        <Col span={8}>
          <WorkflowList onSelectWorkflow={setSelectedWorkflow} />
        </Col>
        <Col span={16}>
          {selectedWorkflow ? (
            <WorkflowDetail path={selectedWorkflow} />
          ) : (
            <Card>
              <Typography.Text type="secondary">
                Select a workflow from the list to view details
              </Typography.Text>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
};
