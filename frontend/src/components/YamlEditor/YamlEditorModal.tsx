import React, { useState, useEffect } from 'react';
import { Modal, Button, Space, Alert, message, Spin, Tag } from 'antd';
import { SaveOutlined, ReloadOutlined, ExpandOutlined, CompressOutlined } from '@ant-design/icons';
import Editor from '@monaco-editor/react';
import { workflowAPI } from '../../api/client';

interface YamlEditorModalProps {
  workflowPath: string;
  open: boolean;
  onClose: () => void;
  onSave?: () => void;
}

export const YamlEditorModal: React.FC<YamlEditorModalProps> = ({
  workflowPath,
  open,
  onClose,
  onSave,
}) => {
  const [content, setContent] = useState<string>('');
  const [originalContent, setOriginalContent] = useState<string>('');
  const [modified, setModified] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fullScreen, setFullScreen] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Load workflow content when modal opens
  useEffect(() => {
    if (open && workflowPath) {
      loadWorkflow();
    }
    // Clean up when modal closes
    return () => {
      if (!open) {
        setContent('');
        setOriginalContent('');
        setError(null);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, workflowPath]);

  // Track changes
  useEffect(() => {
    setHasChanges(content !== originalContent);
  }, [content, originalContent]);

  const loadWorkflow = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await workflowAPI.getRaw(workflowPath);
      setContent(response.content);
      setOriginalContent(response.content);
      setModified(response.modified);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to load workflow';
      setError(errorMessage);
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    try {
      await workflowAPI.updateRaw(workflowPath, content, modified);
      message.success('Workflow saved successfully');
      setOriginalContent(content);
      setHasChanges(false);

      // Reload to get new modification timestamp
      await loadWorkflow();

      // Call onSave callback if provided
      if (onSave) {
        onSave();
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to save workflow';
      setError(errorMessage);
      message.error(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    if (hasChanges) {
      Modal.confirm({
        title: 'Unsaved Changes',
        content: 'You have unsaved changes. Are you sure you want to close?',
        onOk: () => {
          onClose();
          setFullScreen(false);
        },
      });
    } else {
      onClose();
      setFullScreen(false);
    }
  };

  const handleReset = () => {
    if (hasChanges) {
      Modal.confirm({
        title: 'Reset Changes',
        content: 'Are you sure you want to discard all changes?',
        onOk: () => {
          setContent(originalContent);
          setError(null);
        },
      });
    }
  };

  return (
    <Modal
      title={
        <Space>
          <span>Edit Workflow: {workflowPath.split('/').pop()}</span>
          {hasChanges && <Tag color="orange">Modified</Tag>}
        </Space>
      }
      open={open}
      onCancel={handleClose}
      width={fullScreen ? '100vw' : '90vw'}
      style={fullScreen ? { top: 0, padding: 0, maxWidth: '100vw' } : { top: 20 }}
      styles={{
        body: {
          height: fullScreen ? 'calc(100vh - 110px)' : '70vh',
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
        },
      }}
      footer={[
        <Button key="fullscreen" onClick={() => setFullScreen(!fullScreen)}>
          {fullScreen ? <CompressOutlined /> : <ExpandOutlined />}
          {fullScreen ? 'Exit Fullscreen' : 'Fullscreen'}
        </Button>,
        <Button key="reset" onClick={handleReset} disabled={!hasChanges || loading || saving}>
          <ReloadOutlined />
          Reset
        </Button>,
        <Button key="cancel" onClick={handleClose}>
          Cancel
        </Button>,
        <Button
          key="save"
          type="primary"
          onClick={handleSave}
          disabled={!hasChanges || loading || saving}
          loading={saving}
        >
          <SaveOutlined />
          Save
        </Button>,
      ]}
    >
      {error && (
        <Alert
          message="Error"
          description={error}
          type="error"
          showIcon
          closable
          onClose={() => setError(null)}
          style={{ marginBottom: 16 }}
        />
      )}

      {loading ? (
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100%',
          }}
        >
          <Spin size="large" />
        </div>
      ) : (
        <Editor
          height="100%"
          defaultLanguage="yaml"
          language="yaml"
          value={content}
          onChange={(value) => setContent(value || '')}
          theme="vs-light"
          options={{
            fontSize: 14,
            minimap: { enabled: !fullScreen },
            wordWrap: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
            insertSpaces: true,
            formatOnPaste: true,
            formatOnType: true,
          }}
        />
      )}
    </Modal>
  );
};
