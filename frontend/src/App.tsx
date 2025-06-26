// Testing pre-commit hooks
import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider, Layout, Menu, Button, Dropdown, Space } from 'antd';
import {
  AppstoreOutlined,
  PlayCircleOutlined,
  ExperimentOutlined,
  BookOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { WorkflowsPage } from './pages/Workflows';
import { ExecutionsPage } from './pages/Executions';
import { ExecutionDetail } from './pages/Executions/ExecutionDetail';
import { TestingPage } from './pages/Testing';
import { DocumentationPage } from './pages/Documentation';
import { LoginPage } from './pages/Auth/LoginPage';
import { ProtectedRoute } from './components/Auth/ProtectedRoute';
import { useAuthStore } from './stores/auth';
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

function AppContent() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, isAuthenticated } = useAuthStore();

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
    {
      key: 'documentation',
      icon: <BookOutlined />,
      label: 'Documentation',
      path: '/documentation',
    },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      onClick: handleLogout,
    },
  ];

  // Don't show the layout on login page
  if (location.pathname === '/login') {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#001529' }}>
        <div style={{ color: 'white', fontSize: '20px', fontWeight: 'bold' }}>
          SeriesOfTubes
        </div>
        {isAuthenticated && user && (
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Button type="text" style={{ color: 'white' }}>
              <Space>
                <UserOutlined />
                {user.username}
              </Space>
            </Button>
          </Dropdown>
        )}
      </Header>
      <Layout>
        <Sider width={200} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={[location.pathname.split('/')[1] || 'workflows']}
            style={{ height: '100%', borderRight: 0 }}
            items={menuItems.map((item) => ({
              key: item.key,
              icon: item.icon,
              label: item.label,
              onClick: () => navigate(item.path),
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
              <Route path="/workflows" element={
                <ProtectedRoute>
                  <WorkflowsPage />
                </ProtectedRoute>
              } />
              <Route path="/executions" element={
                <ProtectedRoute>
                  <ExecutionsPage />
                </ProtectedRoute>
              } />
              <Route path="/executions/:id" element={
                <ProtectedRoute>
                  <ExecutionDetail />
                </ProtectedRoute>
              } />
              <Route path="/testing" element={
                <ProtectedRoute>
                  <TestingPage />
                </ProtectedRoute>
              } />
              <Route path="/documentation" element={
                <ProtectedRoute>
                  <DocumentationPage />
                </ProtectedRoute>
              } />
              <Route path="/" element={<Navigate to="/workflows" replace />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
}

function App() {
  const { checkAuth } = useAuthStore();

  useEffect(() => {
    // Check auth on mount
    checkAuth();
  }, [checkAuth]);

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider>
        <Router>
          <AppContent />
        </Router>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

export default App;
