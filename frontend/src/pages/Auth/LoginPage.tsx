import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Form, Input, Button, Card, Typography, Tabs, Alert } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons';
import { useAuthStore } from '../../stores/auth';

const { Title } = Typography;

interface LoginFormValues {
  username: string;
  password: string;
}

interface RegisterFormValues {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, register, isLoading, error, clearError } = useAuthStore();
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');
  const [localError, setLocalError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const from = (location.state as any)?.from?.pathname || '/workflows';

  const handleLogin = async (values: LoginFormValues) => {
    try {
      await login(values.username, values.password);
      navigate(from, { replace: true });
    } catch (error: any) {
      console.error('Login error:', error);
      // Show error immediately in case useEffect doesn't trigger
      const errorMessage = error.response?.data?.detail || 'Login failed';
      console.log('Error message:', errorMessage);
      
      // Set local error state to show Alert
      setLocalError(errorMessage);
    }
  };

  const handleRegister = async (values: RegisterFormValues) => {
    try {
      await register(values.username, values.email, values.password);
      setActiveTab('login');
      setSuccessMessage('Registration successful! Please login.');
    } catch (error: any) {
      // Show error immediately in case useEffect doesn't trigger
      const errorMessage = error.response?.data?.detail || 'Registration failed';
      
      // Set local error state to show Alert
      setLocalError(errorMessage);
    }
  };

  // Remove the useEffect that was causing duplicate error messages

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        /* Background will be handled by theme */
      }}
    >
      <Card style={{ width: 400, boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={2} style={{ marginBottom: 8 }}>
            SeriesOfTubes
          </Title>
          <Typography.Text type="secondary">LLM Workflow Orchestration Platform</Typography.Text>
        </div>

        {(error || localError) && (
          <Alert
            message={error || localError}
            type="error"
            showIcon
            closable
            onClose={() => {
              clearError();
              setLocalError(null);
            }}
            style={{ marginBottom: 16 }}
          />
        )}
        
        {successMessage && (
          <Alert
            message={successMessage}
            type="success"
            showIcon
            closable
            onClose={() => setSuccessMessage(null)}
            style={{ marginBottom: 16 }}
          />
        )}

        <Tabs
          activeKey={activeTab}
          onChange={(key) => {
            setActiveTab(key as 'login' | 'register');
            clearError();
            setLocalError(null);
          }}
          items={[
            {
              key: 'login',
              label: 'Login',
              children: (
                <Form name="login" onFinish={handleLogin} autoComplete="off" layout="vertical">
                  <Form.Item
                    name="username"
                    rules={[{ required: true, message: 'Please input your username!' }]}
                  >
                    <Input prefix={<UserOutlined />} placeholder="Username" size="large" />
                  </Form.Item>

                  <Form.Item
                    name="password"
                    rules={[{ required: true, message: 'Please input your password!' }]}
                  >
                    <Input.Password prefix={<LockOutlined />} placeholder="Password" size="large" />
                  </Form.Item>

                  <Form.Item>
                    <Button type="primary" htmlType="submit" loading={isLoading} size="large" block>
                      Log in
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: 'register',
              label: 'Register',
              children: (
                <Form
                  name="register"
                  onFinish={handleRegister}
                  autoComplete="off"
                  layout="vertical"
                >
                  <Form.Item
                    name="username"
                    rules={[
                      { required: true, message: 'Please input your username!' },
                      { min: 3, message: 'Username must be at least 3 characters!' },
                    ]}
                  >
                    <Input prefix={<UserOutlined />} placeholder="Username" size="large" />
                  </Form.Item>

                  <Form.Item
                    name="email"
                    rules={[
                      { required: true, message: 'Please input your email!' },
                      { type: 'email', message: 'Please enter a valid email!' },
                    ]}
                  >
                    <Input prefix={<MailOutlined />} placeholder="Email" size="large" />
                  </Form.Item>

                  <Form.Item
                    name="password"
                    rules={[
                      { required: true, message: 'Please input your password!' },
                      { min: 8, message: 'Password must be at least 8 characters!' },
                    ]}
                  >
                    <Input.Password prefix={<LockOutlined />} placeholder="Password" size="large" />
                  </Form.Item>

                  <Form.Item
                    name="confirmPassword"
                    dependencies={['password']}
                    rules={[
                      { required: true, message: 'Please confirm your password!' },
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          if (!value || getFieldValue('password') === value) {
                            return Promise.resolve();
                          }
                          return Promise.reject(new Error('Passwords do not match!'));
                        },
                      }),
                    ]}
                  >
                    <Input.Password
                      prefix={<LockOutlined />}
                      placeholder="Confirm Password"
                      size="large"
                    />
                  </Form.Item>

                  <Form.Item>
                    <Button type="primary" htmlType="submit" loading={isLoading} size="large" block>
                      Register
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
};
