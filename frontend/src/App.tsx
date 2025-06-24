import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider, Layout, Menu } from 'antd';
import {
  AppstoreOutlined,
  PlayCircleOutlined,
  ExperimentOutlined,
} from '@ant-design/icons';
import { WorkflowsPage } from './pages/Workflows';
import { ExecutionsPage } from './pages/Executions';
import { TestingPage } from './pages/Testing';
import './App.css';

const { Header, Content, Sider } = Layout;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  const menuItems = [
    {
      key: 'workflows',
      icon: <AppstoreOutlined />,
      label: 'Workflows',
      path: '/workflows',
    },
    {
      key: 'executions',
      icon: <PlayCircleOutlined />,
      label: 'Executions',
      path: '/executions',
    },
    {
      key: 'testing',
      icon: <ExperimentOutlined />,
      label: 'Testing',
      path: '/testing',
    },
  ];

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider>
        <Router>
          <Layout style={{ minHeight: '100vh' }}>
            <Header style={{ display: 'flex', alignItems: 'center', background: '#001529' }}>
              <div style={{ color: 'white', fontSize: '20px', fontWeight: 'bold' }}>
                SeriesOfTubes
              </div>
            </Header>
            <Layout>
              <Sider width={200} style={{ background: '#fff' }}>
                <Menu
                  mode="inline"
                  defaultSelectedKeys={['workflows']}
                  style={{ height: '100%', borderRight: 0 }}
                  items={menuItems.map(item => ({
                    key: item.key,
                    icon: item.icon,
                    label: <a href={item.path}>{item.label}</a>,
                  }))}
                />
              </Sider>
              <Layout style={{ padding: '24px', background: '#f0f2f5' }}>
                <Content
                  style={{
                    padding: 24,
                    margin: 0,
                    minHeight: 280,
                    background: '#fff',
                    borderRadius: 8,
                  }}
                >
                  <Routes>
                    <Route path="/workflows" element={<WorkflowsPage />} />
                    <Route path="/executions" element={<ExecutionsPage />} />
                    <Route path="/testing" element={<TestingPage />} />
                    <Route path="/" element={<Navigate to="/workflows" replace />} />
                  </Routes>
                </Content>
              </Layout>
            </Layout>
          </Layout>
        </Router>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

export default App;
