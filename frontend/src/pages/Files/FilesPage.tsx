import React, { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Upload,
  message,
  Space,
  Card,
  Typography,
  Modal,
  Input,
  Tag,
  Dropdown,
  Menu,
} from 'antd';
import {
  UploadOutlined,
  DownloadOutlined,
  DeleteOutlined,
  FileOutlined,
  FileTextOutlined,
  FileImageOutlined,
  FilePdfOutlined,
  FileExcelOutlined,
  FileWordOutlined,
  MoreOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import type { UploadProps, ColumnsType } from 'antd/es/upload';
import { useAuthStore } from '../../stores/authStore';
import api from '../../api/client';

const { Title } = Typography;
const { Search } = Input;

interface FileInfo {
  file_id: string;
  filename: string;
  size: number;
  content_type?: string;
  last_modified: string;
  is_public: boolean;
}

interface FileListResponse {
  success: boolean;
  message: string;
  files: FileInfo[];
  total: number;
}

const FilesPage: React.FC = () => {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchPrefix, setSearchPrefix] = useState('');
  const [selectedFile, setSelectedFile] = useState<FileInfo | null>(null);
  const { token } = useAuthStore();

  const fetchFiles = async () => {
    setLoading(true);
    try {
      const response = await api.get<FileListResponse>('/api/files', {
        params: { prefix: searchPrefix, limit: 100 },
      });
      setFiles(response.data.files);
    } catch (error) {
      message.error('Failed to fetch files');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, [searchPrefix]);

  const getFileIcon = (contentType?: string, filename?: string) => {
    if (!contentType && filename) {
      const ext = filename.split('.').pop()?.toLowerCase();
      if (['jpg', 'jpeg', 'png', 'gif', 'svg'].includes(ext || '')) {
        return <FileImageOutlined />;
      }
      if (ext === 'pdf') return <FilePdfOutlined />;
      if (['xls', 'xlsx'].includes(ext || '')) return <FileExcelOutlined />;
      if (['doc', 'docx'].includes(ext || '')) return <FileWordOutlined />;
      if (['txt', 'json', 'yaml', 'yml'].includes(ext || '')) return <FileTextOutlined />;
    }
    
    if (contentType?.startsWith('image/')) return <FileImageOutlined />;
    if (contentType === 'application/pdf') return <FilePdfOutlined />;
    if (contentType?.includes('spreadsheet')) return <FileExcelOutlined />;
    if (contentType?.includes('word')) return <FileWordOutlined />;
    if (contentType?.startsWith('text/')) return <FileTextOutlined />;
    
    return <FileOutlined />;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleDownload = async (fileId: string, filename: string) => {
    try {
      const response = await api.get(`/api/files/${fileId}/download`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      message.success('File downloaded successfully');
    } catch (error) {
      message.error('Failed to download file');
    }
  };

  const handleDelete = async (fileId: string) => {
    Modal.confirm({
      title: 'Delete File',
      content: 'Are you sure you want to delete this file?',
      onOk: async () => {
        try {
          await api.delete(`/api/files/${fileId}`);
          message.success('File deleted successfully');
          fetchFiles();
        } catch (error) {
          message.error('Failed to delete file');
        }
      },
    });
  };

  const handleGetUrl = async (fileId: string) => {
    try {
      const response = await api.get<{ url: string; expires_in: number }>(
        `/api/files/${fileId}/url`
      );
      
      Modal.info({
        title: 'File URL',
        width: 600,
        content: (
          <div>
            <p>This URL expires in {response.data.expires_in / 3600} hours:</p>
            <Input.TextArea
              value={response.data.url}
              readOnly
              autoSize={{ minRows: 3, maxRows: 6 }}
              style={{ marginTop: 8 }}
            />
            <Button
              type="primary"
              style={{ marginTop: 8 }}
              onClick={() => {
                navigator.clipboard.writeText(response.data.url);
                message.success('URL copied to clipboard');
              }}
            >
              Copy URL
            </Button>
          </div>
        ),
      });
    } catch (error) {
      message.error('Failed to get file URL');
    }
  };

  const uploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    action: `${api.defaults.baseURL}/api/files/upload`,
    headers: {
      Authorization: `Bearer ${token}`,
    },
    onChange(info) {
      if (info.file.status === 'done') {
        message.success(`${info.file.name} uploaded successfully`);
        fetchFiles();
      } else if (info.file.status === 'error') {
        message.error(`${info.file.name} upload failed`);
      }
    },
  };

  const columns: ColumnsType<FileInfo> = [
    {
      title: 'Name',
      dataIndex: 'filename',
      key: 'filename',
      render: (text, record) => (
        <Space>
          {getFileIcon(record.content_type, text)}
          <span>{text}</span>
          {record.is_public && <Tag color="blue">Public</Tag>}
        </Space>
      ),
      sorter: (a, b) => a.filename.localeCompare(b.filename),
    },
    {
      title: 'Size',
      dataIndex: 'size',
      key: 'size',
      render: formatFileSize,
      sorter: (a, b) => a.size - b.size,
      width: 100,
    },
    {
      title: 'Type',
      dataIndex: 'content_type',
      key: 'content_type',
      render: (text) => text || 'Unknown',
      width: 150,
    },
    {
      title: 'Modified',
      dataIndex: 'last_modified',
      key: 'last_modified',
      render: (text) => new Date(text).toLocaleString(),
      sorter: (a, b) => new Date(a.last_modified).getTime() - new Date(b.last_modified).getTime(),
      width: 200,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_, record) => (
        <Dropdown
          menu={{
            items: [
              {
                key: 'download',
                icon: <DownloadOutlined />,
                label: 'Download',
                onClick: () => handleDownload(record.file_id, record.filename),
              },
              {
                key: 'url',
                icon: <FileOutlined />,
                label: 'Get URL',
                onClick: () => handleGetUrl(record.file_id),
              },
              {
                key: 'divider',
                type: 'divider',
              },
              {
                key: 'delete',
                icon: <DeleteOutlined />,
                label: 'Delete',
                danger: true,
                onClick: () => handleDelete(record.file_id),
              },
            ],
          }}
        >
          <Button icon={<MoreOutlined />} />
        </Dropdown>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <div style={{ marginBottom: 16 }}>
          <Title level={4} style={{ margin: 0 }}>
            Files
          </Title>
        </div>

        <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Upload {...uploadProps}>
              <Button icon={<UploadOutlined />}>Upload File</Button>
            </Upload>
            <Button onClick={fetchFiles} loading={loading}>
              Refresh
            </Button>
          </Space>
          
          <Search
            placeholder="Search files by prefix"
            allowClear
            enterButton
            style={{ width: 300 }}
            onSearch={setSearchPrefix}
            prefix={<SearchOutlined />}
          />
        </Space>

        <Table
          columns={columns}
          dataSource={files}
          rowKey="file_id"
          loading={loading}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} files`,
          }}
        />
      </Card>
    </div>
  );
};

export default FilesPage;