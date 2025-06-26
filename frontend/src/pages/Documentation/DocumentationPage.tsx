import React, { useState, useEffect } from 'react';
import { Layout, Menu, Typography, Card, Spin, Alert } from 'antd';
import { FileTextOutlined, BookOutlined, ApiOutlined, CodeOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { MenuProps } from 'antd';
import { useThemeStore } from '../../stores/theme';

const { Title } = Typography;
const { Sider, Content } = Layout;

interface DocFile {
  path: string;
  title: string;
  category: string;
}

const docFiles: DocFile[] = [
  // Quick Reference
  {
    path: '/docs/reference/quick-reference.md',
    title: 'Quick Reference',
    category: 'Getting Started',
  },
  {
    path: '/docs/guides/workflow-structure.md',
    title: 'Workflow Structure',
    category: 'Getting Started',
  },

  // Node Types
  { path: '/docs/reference/nodes/llm.md', title: 'LLM Node', category: 'Node Types' },
  { path: '/docs/reference/nodes/http.md', title: 'HTTP Node', category: 'Node Types' },
  { path: '/docs/reference/nodes/route.md', title: 'Route Node', category: 'Node Types' },
  { path: '/docs/reference/nodes/file.md', title: 'File Node', category: 'Node Types' },
  { path: '/docs/reference/nodes/python.md', title: 'Python Node', category: 'Node Types' },
];

const getIcon = (category: string) => {
  switch (category) {
    case 'Getting Started':
      return <BookOutlined />;
    case 'Node Types':
      return <ApiOutlined />;
    default:
      return <FileTextOutlined />;
  }
};

export const DocumentationPage: React.FC = () => {
  const [selectedDoc, setSelectedDoc] = useState<DocFile>(docFiles[0]);
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { mode: themeMode } = useThemeStore();

  useEffect(() => {
    const fetchDoc = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(selectedDoc.path);
        if (!response.ok) {
          throw new Error(`Failed to load documentation: ${response.statusText}`);
        }
        const text = await response.text();
        setContent(text);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load documentation');
        setContent('');
      } finally {
        setLoading(false);
      }
    };

    fetchDoc();
  }, [selectedDoc]);

  // Group documents by category
  const menuItems: MenuProps['items'] = Object.entries(
    docFiles.reduce(
      (acc, doc) => {
        if (!acc[doc.category]) {
          acc[doc.category] = [];
        }
        acc[doc.category].push(doc);
        return acc;
      },
      {} as Record<string, DocFile[]>
    )
  ).map(([category, docs]) => ({
    key: category,
    label: category,
    icon: getIcon(category),
    children: docs.map((doc) => ({
      key: doc.path,
      label: doc.title,
      onClick: () => setSelectedDoc(doc),
    })),
  }));

  return (
    <Layout style={{ height: '100%' }}>
      <Sider width={250}>
        <div style={{ padding: '16px' }}>
          <Title level={4}>Documentation</Title>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedDoc.path]}
          defaultOpenKeys={['Getting Started', 'Node Types']}
          style={{ height: 'calc(100% - 64px)', borderRight: 0 }}
          items={menuItems}
        />
      </Sider>
      <Layout style={{ padding: '24px' }}>
        <Content
          style={{
            padding: 24,
            margin: 0,
            minHeight: 280,
            borderRadius: 8,
            overflow: 'auto',
          }}
        >
          {loading && (
            <div style={{ textAlign: 'center', padding: '50px' }}>
              <Spin size="large" />
            </div>
          )}

          {error && <Alert message="Error" description={error} type="error" showIcon />}

          {!loading && !error && (
            <div className="markdown-body" style={{ maxWidth: '900px', margin: '0 auto' }}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // Custom rendering for code blocks
                  code({ inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline && match ? (
                      <Card
                        size="small"
                        style={{
                          marginBottom: 16,
                          fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                        }}
                      >
                        <div
                          style={{
                            fontSize: '12px',
                            marginBottom: '8px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            opacity: 0.7,
                          }}
                        >
                          <CodeOutlined />
                          {match[1]}
                        </div>
                        <pre style={{ margin: 0, overflow: 'auto' }}>
                          <code {...props}>{children}</code>
                        </pre>
                      </Card>
                    ) : (
                      <code
                        {...props}
                        style={{
                          backgroundColor: themeMode === 'dark' ? '#374151' : '#f1f5f9',
                          color: themeMode === 'dark' ? '#f3f4f6' : '#374151',
                          padding: '3px 6px',
                          borderRadius: '4px',
                          fontFamily: 'JetBrains Mono, Monaco, Consolas, "Courier New", monospace',
                          fontSize: '0.85em',
                          fontWeight: '500',
                          border: themeMode === 'dark' ? '1px solid #4b5563' : '1px solid #e2e8f0',
                        }}
                      >
                        {children}
                      </code>
                    );
                  },
                  // Custom table rendering
                  table({ children }) {
                    return (
                      <div style={{ overflowX: 'auto', marginBottom: 16 }}>
                        <table
                          style={{
                            width: '100%',
                            borderCollapse: 'collapse',
                            border: `1px solid ${themeMode === 'dark' ? '#4b5563' : '#e2e8f0'}`,
                          }}
                        >
                          {children}
                        </table>
                      </div>
                    );
                  },
                  th({ children }) {
                    return (
                      <th
                        style={{
                          padding: '12px 16px',
                          textAlign: 'left',
                          backgroundColor: themeMode === 'dark' ? '#374151' : '#f8fafc',
                          borderBottom: `2px solid ${themeMode === 'dark' ? '#4b5563' : '#e2e8f0'}`,
                          borderRight: `1px solid ${themeMode === 'dark' ? '#4b5563' : '#e2e8f0'}`,
                          fontWeight: 600,
                          fontSize: '14px',
                          color: themeMode === 'dark' ? '#f9fafb' : '#374151',
                        }}
                      >
                        {children}
                      </th>
                    );
                  },
                  td({ children }) {
                    return (
                      <td
                        style={{
                          padding: '12px 16px',
                          borderBottom: `1px solid ${themeMode === 'dark' ? '#4b5563' : '#e2e8f0'}`,
                          borderRight: `1px solid ${themeMode === 'dark' ? '#4b5563' : '#e2e8f0'}`,
                          fontSize: '14px',
                          lineHeight: '1.5',
                        }}
                      >
                        {children}
                      </td>
                    );
                  },
                  // Custom heading rendering
                  h1({ children }) {
                    return <Title level={1}>{children}</Title>;
                  },
                  h2({ children }) {
                    return <Title level={2}>{children}</Title>;
                  },
                  h3({ children }) {
                    return <Title level={3}>{children}</Title>;
                  },
                  // Custom list styling
                  ul({ children }) {
                    return (
                      <ul
                        style={{
                          paddingLeft: '24px',
                          marginBottom: '16px',
                        }}
                      >
                        {children}
                      </ul>
                    );
                  },
                  ol({ children }) {
                    return (
                      <ol
                        style={{
                          paddingLeft: '24px',
                          marginBottom: '16px',
                        }}
                      >
                        {children}
                      </ol>
                    );
                  },
                  li({ children }) {
                    return (
                      <li
                        style={{
                          marginBottom: '8px',
                          lineHeight: '1.6',
                          fontSize: '14px',
                        }}
                      >
                        {children}
                      </li>
                    );
                  },
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          )}
        </Content>
      </Layout>
    </Layout>
  );
};
