// Testing pre-commit hooks
import React, { useEffect } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useLocation,
} from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider, Layout, Menu, Button, Dropdown, Space, Input, theme } from 'antd';
import {
  AppstoreOutlined,
  PlayCircleOutlined,
  ExperimentOutlined,
  BookOutlined,
  UserOutlined,
  LogoutOutlined,
  MoonOutlined,
  SunOutlined,
  SearchOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { WorkflowsPage } from './pages/Workflows';
import { ExecutionsPage } from './pages/Executions';
import { ExecutionDetail } from './pages/Executions/ExecutionDetail';
import { TestingPage } from './pages/Testing';
import { DocumentationPage } from './pages/Documentation';
import { LoginPage } from './pages/Auth/LoginPage';
import { ProtectedRoute } from './components/Auth/ProtectedRoute';
import { useAuthStore } from './stores/auth';
import { useThemeStore } from './stores/theme';
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

// Modern theme configurations
const getThemeConfig = (isDark: boolean) => ({
  algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
  token: {
    // Color palette
    colorPrimary: '#4f46e5', // Indigo 600 - strong, professional
    colorSuccess: '#059669', // Emerald 600 - clear success
    colorWarning: '#d97706', // Amber 600 - noticeable warnings
    colorError: '#dc2626', // Red 600 - clear errors
    colorInfo: '#0284c7', // Sky 600 - informational blue

    // Background colors
    colorBgBase: isDark ? '#0f172a' : '#ffffff', // Slate 900 / White
    colorBgContainer: isDark ? '#1e293b' : '#ffffff', // Slate 800 / White
    colorBgElevated: isDark ? '#334155' : '#f8fafc', // Slate 700 / Slate 50
    colorBgLayout: isDark ? '#0f172a' : '#f8fafc', // Slate 900 / Slate 50
    colorBgSpotlight: isDark ? '#1e293b' : '#f1f5f9', // Slate 800 / Slate 100

    // Text colors
    colorText: isDark ? '#f1f5f9' : '#0f172a', // Slate 100 / Slate 900
    colorTextSecondary: isDark ? '#cbd5e1' : '#475569', // Slate 300 / Slate 600
    colorTextTertiary: isDark ? '#94a3b8' : '#64748b', // Slate 400 / Slate 500
    colorTextQuaternary: isDark ? '#64748b' : '#94a3b8', // Slate 500 / Slate 400

    // Border colors
    colorBorder: isDark ? '#475569' : '#e2e8f0', // Slate 600 / Slate 200
    colorBorderSecondary: isDark ? '#334155' : '#f1f5f9', // Slate 700 / Slate 100

    // Typography and spacing
    borderRadius: 8,
    borderRadiusLG: 12,
    borderRadiusSM: 6,
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontSize: 14,
    fontSizeLG: 16,
    fontSizeXL: 20,

    // Shadows
    boxShadow: isDark
      ? '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)'
      : '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
    boxShadowSecondary: isDark
      ? '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.3)'
      : '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',

    // Spacing system (4px base unit)
    padding: 16,
    paddingLG: 24,
    paddingXL: 32,
    margin: 16,
    marginLG: 24,
    marginXL: 32,
  },
  components: {
    Layout: {
      headerBg: isDark ? '#1e293b' : '#ffffff', // Slate 800 / White
      headerHeight: 72,
      headerPadding: '0 32px',
      siderBg: isDark ? '#0f172a' : '#f8fafc', // Slate 900 / Slate 50
      bodyBg: isDark ? '#0f172a' : '#f8fafc', // Slate 900 / Slate 50
      footerBg: isDark ? '#1e293b' : '#ffffff', // Slate 800 / White
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: isDark ? '#4f46e5' : '#eef2ff', // Indigo 600 / Indigo 50
      itemHoverBg: isDark ? '#334155' : '#f1f5f9', // Slate 700 / Slate 100
      itemSelectedColor: isDark ? '#ffffff' : '#4f46e5', // White / Indigo 600
      itemColor: isDark ? '#e2e8f0' : '#374151', // Slate 200 / Slate 700 - much higher contrast
      itemHoverColor: isDark ? '#f1f5f9' : '#1e293b', // Slate 100 / Slate 800 - even higher on hover
      // Submenu specific styling
      subMenuItemBg: 'transparent',
      groupTitleColor: isDark ? '#f1f5f9' : '#1e293b', // Even higher contrast for submenu titles
      iconSize: 18,
      fontSize: 14,
      fontWeight: 500,
      itemHeight: 44,
      itemMarginInline: 8,
    },
    Card: {
      headerBg: 'transparent',
      boxShadow: isDark
        ? '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)'
        : '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
      borderRadius: 12,
      paddingLG: 24,
    },
    Button: {
      borderRadius: 8,
      fontWeight: 500,
      paddingInline: 20,
      paddingBlock: 8,
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
    },
    Input: {
      borderRadius: 8,
      paddingInline: 16,
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
    },
    Select: {
      borderRadius: 8,
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
    },
    Tag: {
      borderRadius: 6,
      paddingInline: 8,
      fontSize: 12,
      fontWeight: 500,
    },
    Typography: {
      titleMarginBottom: 16,
      titleMarginTop: 0,
    },
    Modal: {
      borderRadius: 12,
      paddingLG: 32,
    },
    Dropdown: {
      borderRadius: 8,
      boxShadow: isDark
        ? '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.3)'
        : '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    },
  },
});

function AppContent() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, isAuthenticated } = useAuthStore();
  const { mode: themeMode, toggleTheme } = useThemeStore();

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
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 32px',
          height: 72,
          borderBottom: `1px solid ${themeMode === 'dark' ? '#334155' : '#e2e8f0'}`,
          boxShadow:
            themeMode === 'dark'
              ? '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)'
              : '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
        }}
      >
        {/* Left side - Logo and brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              cursor: 'pointer',
            }}
            onClick={() => navigate('/workflows')}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontSize: '16px',
              }}
            >
              <SwapOutlined />
            </div>
            <span
              style={{
                fontSize: '20px',
                fontWeight: '700',
                letterSpacing: '-0.025em',
                background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              SeriesOfTubes
            </span>
          </div>

          {/* Global search */}
          {isAuthenticated && (
            <div style={{ width: '320px' }}>
              <Input
                placeholder="Search workflows..."
                prefix={
                  <SearchOutlined style={{ color: themeMode === 'dark' ? '#94a3b8' : '#64748b' }} />
                }
                style={{
                  borderRadius: '8px',
                  backgroundColor: themeMode === 'dark' ? '#334155' : '#f8fafc',
                  border: `1px solid ${themeMode === 'dark' ? '#475569' : '#e2e8f0'}`,
                }}
                size="large"
              />
            </div>
          )}
        </div>

        {/* Right side - Actions and user */}
        {isAuthenticated && user && (
          <Space size="large">
            {/* Theme toggle */}
            <Button
              type="text"
              icon={themeMode === 'dark' ? <SunOutlined /> : <MoonOutlined />}
              onClick={toggleTheme}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '40px',
                height: '40px',
                borderRadius: '8px',
              }}
              title={`Switch to ${themeMode === 'dark' ? 'light' : 'dark'} mode`}
            />

            {/* User dropdown */}
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Button
                type="text"
                style={{
                  height: '40px',
                  borderRadius: '8px',
                  fontWeight: '500',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <div
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontSize: '12px',
                    fontWeight: '600',
                  }}
                >
                  {user.username.charAt(0).toUpperCase()}
                </div>
                <span>{user.username}</span>
              </Button>
            </Dropdown>
          </Space>
        )}
      </Header>
      <Layout>
        <Sider
          width={280}
          style={{
            borderRight: `1px solid ${themeMode === 'dark' ? '#334155' : '#e2e8f0'}`,
          }}
        >
          <Menu
            mode="inline"
            selectedKeys={[location.pathname.split('/')[1] || 'workflows']}
            style={{
              height: '100%',
              borderRight: 0,
              padding: '24px 16px',
              background: 'transparent',
            }}
            items={menuItems.map((item) => ({
              key: item.key,
              icon: item.icon,
              label: item.label,
              onClick: () => navigate(item.path),
              style: {
                margin: '4px 0',
                borderRadius: '12px',
                fontWeight: '500',
                height: '44px',
                display: 'flex',
                alignItems: 'center',
              },
            }))}
          />
        </Sider>
        <Layout style={{ padding: '32px' }}>
          <Content
            style={{
              padding: 32,
              margin: 0,
              minHeight: 280,
              borderRadius: 16,
              maxWidth: '1400px',
              width: '100%',
            }}
          >
            <Routes>
              <Route
                path="/workflows"
                element={
                  <ProtectedRoute>
                    <WorkflowsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/executions"
                element={
                  <ProtectedRoute>
                    <ExecutionsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/executions/:id"
                element={
                  <ProtectedRoute>
                    <ExecutionDetail />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/testing"
                element={
                  <ProtectedRoute>
                    <TestingPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/documentation"
                element={
                  <ProtectedRoute>
                    <DocumentationPage />
                  </ProtectedRoute>
                }
              />
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
  const { mode: themeMode } = useThemeStore();

  useEffect(() => {
    // Check auth on mount
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    // Set data-theme attribute on document body for CSS targeting
    document.body.setAttribute('data-theme', themeMode);
    return () => {
      document.body.removeAttribute('data-theme');
    };
  }, [themeMode]);

  const currentTheme = getThemeConfig(themeMode === 'dark');

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider theme={currentTheme}>
        <Router>
          <AppContent />
        </Router>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

export default App;
