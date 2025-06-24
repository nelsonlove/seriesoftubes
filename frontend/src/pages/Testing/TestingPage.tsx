import React from 'react';
import { Typography } from 'antd';

const { Title } = Typography;

export const TestingPage: React.FC = () => {
  return (
    <div>
      <Title level={2}>Testing</Title>
      <Typography.Text>Workflow testing interface coming soon...</Typography.Text>
    </div>
  );
};
