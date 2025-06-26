import React, { useState } from 'react';
import {
  Modal,
  Tabs,
  Form,
  Input,
  Switch,
  Button,
  Select,
  Upload,
  message,
  Space,
  Typography,
} from 'antd';
import {
  FileAddOutlined,
  UploadOutlined,
  InboxOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import Editor from '@monaco-editor/react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { workflowAPI } from '../../api/client';
import { workflowTemplates } from '../../templates/workflows';
import type { UploadFile, UploadProps } from 'antd';

const { Text } = Typography;
const { Dragger } = Upload;

interface NewWorkflowModalProps {
  visible: boolean;
  onClose: () => void;
  onSuccess?: (workflowId: string) => void;
}

export const NewWorkflowModal: React.FC<NewWorkflowModalProps> = ({
  visible,
  onClose,
  onSuccess,
}) => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'create' | 'upload'>('create');
  const [yamlContent, setYamlContent] = useState<string>('');
  const [isPublic, setIsPublic] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  // Create workflow mutation
  const createMutation = useMutation({
    mutationFn: ({ content, isPublic }: { content: string; isPublic: boolean }) =>
      workflowAPI.create(content, isPublic),
    onSuccess: (data) => {
      message.success(`Workflow "${data.name}" created successfully!`);
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      onSuccess?.(data.id);
      handleReset();
      onClose();
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to create workflow');
    },
  });

  // Upload file mutation
  const uploadMutation = useMutation({
    mutationFn: ({ file, isPublic }: { file: File; isPublic: boolean }) =>
      workflowAPI.uploadFile(file, isPublic),
    onSuccess: (data) => {
      message.success(`Workflow "${data.name}" uploaded successfully!`);
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      onSuccess?.(data.id);
      handleReset();
      onClose();
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to upload workflow');
    },
  });

  const handleReset = () => {
    setYamlContent('');
    setIsPublic(false);
    setFileList([]);
  };

  const handleTemplateSelect = (templateYaml: string) => {
    setYamlContent(templateYaml);
  };

  const handleCreate = () => {
    if (!yamlContent.trim()) {
      message.error('Please enter workflow YAML content');
      return;
    }
    createMutation.mutate({ content: yamlContent, isPublic });
  };

  const handleUpload = () => {
    if (fileList.length === 0) {
      message.error('Please select a file to upload');
      return;
    }
    const file = fileList[0].originFileObj as File;
    uploadMutation.mutate({ file, isPublic });
  };

  const uploadProps: UploadProps = {
    accept: '.yaml,.yml,.tubes,.zip',
    maxCount: 1,
    fileList,
    beforeUpload: (file) => {
      const isValidType =
        file.name.endsWith('.yaml') ||
        file.name.endsWith('.yml') ||
        file.name.endsWith('.tubes') ||
        file.name.endsWith('.zip');
      
      if (!isValidType) {
        message.error('Please upload a .yaml, .yml, .tubes, or .zip file');
        return Upload.LIST_IGNORE;
      }

      const isLt10M = file.size / 1024 / 1024 < 10;
      if (!isLt10M) {
        message.error('File must be smaller than 10MB');
        return Upload.LIST_IGNORE;
      }

      return false; // Prevent auto upload
    },
    onChange: ({ fileList }) => setFileList(fileList),
    onRemove: () => {
      setFileList([]);
    },
  };

  return (
    <Modal
      title={
        <Space>
          <FileAddOutlined />
          New Workflow
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={800}
      footer={null}
      destroyOnClose
    >
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'create' | 'upload')}
        items={[
          {
            key: 'create',
            label: (
              <Space>
                <CodeOutlined />
                Create New
              </Space>
            ),
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size="large">
                <Form layout="vertical">
                  <Form.Item label="Template (Optional)">
                    <Select
                      placeholder="Select a template to start with"
                      allowClear
                      onChange={(value) => {
                        if (value) {
                          const template = workflowTemplates.find((t) => t.yaml === value);
                          if (template) {
                            handleTemplateSelect(template.yaml);
                          }
                        }
                      }}
                    >
                      {workflowTemplates.map((template, index) => (
                        <Select.Option key={index} value={template.yaml}>
                          <div>
                            <div style={{ fontWeight: 'bold' }}>{template.name}</div>
                            <div style={{ fontSize: '12px', color: '#666' }}>
                              {template.description}
                            </div>
                          </div>
                        </Select.Option>
                      ))}
                    </Select>
                  </Form.Item>

                  <Form.Item
                    label="Workflow YAML"
                    required
                    help="Define your workflow structure in YAML format"
                  >
                    <div style={{ border: '1px solid #d9d9d9', borderRadius: 4 }}>
                      <Editor
                        height="400px"
                        defaultLanguage="yaml"
                        value={yamlContent}
                        onChange={(value) => setYamlContent(value || '')}
                        options={{
                          minimap: { enabled: false },
                          fontSize: 14,
                          wordWrap: 'on',
                          lineNumbers: 'on',
                          scrollBeyondLastLine: false,
                          automaticLayout: true,
                        }}
                        theme="vs-dark"
                      />
                    </div>
                  </Form.Item>

                  <Form.Item>
                    <Space>
                      <Switch
                        checked={isPublic}
                        onChange={setIsPublic}
                        checkedChildren="Public"
                        unCheckedChildren="Private"
                      />
                      <Text type="secondary">
                        {isPublic
                          ? 'This workflow will be visible to all users'
                          : 'This workflow will be private to you'}
                      </Text>
                    </Space>
                  </Form.Item>
                </Form>

                <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
                  <Button onClick={onClose}>Cancel</Button>
                  <Button
                    type="primary"
                    icon={<FileAddOutlined />}
                    onClick={handleCreate}
                    loading={createMutation.isPending}
                  >
                    Create Workflow
                  </Button>
                </Space>
              </Space>
            ),
          },
          {
            key: 'upload',
            label: (
              <Space>
                <UploadOutlined />
                Upload File
              </Space>
            ),
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size="large">
                <Form layout="vertical">
                  <Form.Item
                    label="Upload Workflow File"
                    required
                    help="Supported formats: .yaml, .yml, .tubes (package), .zip"
                  >
                    <Dragger {...uploadProps}>
                      <p className="ant-upload-drag-icon">
                        <InboxOutlined />
                      </p>
                      <p className="ant-upload-text">
                        Click or drag file to this area to upload
                      </p>
                      <p className="ant-upload-hint">
                        Support for YAML workflow files or .tubes packages
                      </p>
                    </Dragger>
                  </Form.Item>

                  <Form.Item>
                    <Space>
                      <Switch
                        checked={isPublic}
                        onChange={setIsPublic}
                        checkedChildren="Public"
                        unCheckedChildren="Private"
                      />
                      <Text type="secondary">
                        {isPublic
                          ? 'This workflow will be visible to all users'
                          : 'This workflow will be private to you'}
                      </Text>
                    </Space>
                  </Form.Item>
                </Form>

                <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
                  <Button onClick={onClose}>Cancel</Button>
                  <Button
                    type="primary"
                    icon={<UploadOutlined />}
                    onClick={handleUpload}
                    loading={uploadMutation.isPending}
                    disabled={fileList.length === 0}
                  >
                    Upload Workflow
                  </Button>
                </Space>
              </Space>
            ),
          },
        ]}
      />
    </Modal>
  );
};