"""Tests for file node security integration"""

import tempfile
from pathlib import Path

import pytest

from seriesoftubes.file_security import FileSecurityConfig
from seriesoftubes.models import FileNodeConfig, Node, NodeType
from seriesoftubes.nodes.file import FileNodeExecutor


class TestFileNodeSecurity:
    """Test file node security features"""

    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            
            # Create allowed directory
            allowed_dir = base / "allowed"
            allowed_dir.mkdir()
            
            # Create test files
            (allowed_dir / "data.json").write_text('{"key": "value"}')
            (allowed_dir / "test.txt").write_text("Hello World")
            (allowed_dir / "numbers.csv").write_text("id,value\n1,100\n2,200")
            
            # Create denied directory
            denied_dir = base / "denied"
            denied_dir.mkdir()
            (denied_dir / "secret.key").write_text("secret_data")
            (denied_dir / "passwords.txt").write_text("admin:123")
            
            # Create file in base dir
            (base / "root.txt").write_text("root file")
            
            yield base, allowed_dir, denied_dir

    @pytest.fixture
    def secure_executor(self, temp_files):
        """Create executor with security configuration"""
        base, allowed_dir, _ = temp_files
        config = FileSecurityConfig(
            allowed_base_dirs=[str(allowed_dir)],
            denied_patterns=["*.key", "*password*", "*.secret"],
        )
        return FileNodeExecutor(config)

    @pytest.fixture
    def mock_context(self):
        """Create mock context"""
        class MockContext:
            def __init__(self):
                self.inputs = {"pattern": "*.txt"}
                self.outputs = {}
        return MockContext()

    async def test_allowed_file_access(self, secure_executor, mock_context, temp_files):
        """Test accessing allowed files"""
        _, allowed_dir, _ = temp_files
        
        node = Node(
            name="read_file",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(allowed_dir / "data.json"),
                format_type="json",
            ),
        )
        
        result = await secure_executor.execute(node, mock_context)
        assert result.success
        assert result.output["data"]["key"] == "value"

    async def test_denied_directory_access(self, secure_executor, mock_context, temp_files):
        """Test that access to denied directories is blocked"""
        _, _, denied_dir = temp_files
        
        node = Node(
            name="read_file",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(denied_dir / "secret.key"),
                format_type="txt",
            ),
        )
        
        result = await secure_executor.execute(node, mock_context)
        assert not result.success
        assert "outside allowed directories" in result.error

    async def test_path_traversal_blocked(self, secure_executor, mock_context, temp_files):
        """Test that path traversal attempts are blocked"""
        _, allowed_dir, _ = temp_files
        
        # Try to escape allowed directory
        node = Node(
            name="read_file",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(allowed_dir / ".." / ".." / "root.txt"),
                format_type="txt",
            ),
        )
        
        result = await secure_executor.execute(node, mock_context)
        assert not result.success
        assert "path traversal" in result.error.lower()

    async def test_denied_pattern_blocked(self, temp_files, mock_context):
        """Test that denied patterns are blocked even in allowed directories"""
        base, allowed_dir, _ = temp_files
        
        # Create a file with denied pattern in allowed directory
        (allowed_dir / "passwords.txt").write_text("user:pass")
        
        # Create executor that allows the directory
        config = FileSecurityConfig(
            allowed_base_dirs=[str(allowed_dir)],
            denied_patterns=["*password*"],
        )
        executor = FileNodeExecutor(config)
        
        node = Node(
            name="read_file",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(allowed_dir / "passwords.txt"),
                format_type="txt",
            ),
        )
        
        result = await executor.execute(node, mock_context)
        assert not result.success
        assert "denied pattern" in result.error.lower()

    async def test_glob_pattern_security(self, secure_executor, mock_context, temp_files):
        """Test glob patterns respect security boundaries"""
        _, allowed_dir, _ = temp_files
        
        # Valid glob within allowed directory
        node = Node(
            name="read_files",
            type=NodeType.FILE,
            config=FileNodeConfig(
                pattern=str(allowed_dir / "*.txt"),
                format_type="txt",
                merge=True,
            ),
        )
        
        result = await secure_executor.execute(node, mock_context)
        assert result.success
        # When merge=True with single txt file, data is the content directly
        assert result.output["data"] == "Hello World"
        
        # Try glob that would escape allowed directory
        node_escape = Node(
            name="read_files",
            type=NodeType.FILE,
            config=FileNodeConfig(
                pattern=str(allowed_dir / ".." / "*" / "*.txt"),
                format_type="txt",
                merge=True,
            ),
        )
        
        result_escape = await secure_executor.execute(node_escape, mock_context)
        assert not result_escape.success

    async def test_symlink_handling(self, temp_files, mock_context):
        """Test symlink security"""
        import os
        if os.name == 'nt':  # Windows
            pytest.skip("Symlink test requires Unix-like OS")
        
        base, allowed_dir, denied_dir = temp_files
        
        # Create symlink from allowed to denied directory
        symlink = allowed_dir / "link_to_secret"
        symlink.symlink_to(denied_dir / "secret.key")
        
        # Executor that disallows symlinks
        config = FileSecurityConfig(
            allowed_base_dirs=[str(allowed_dir)],
            allow_symlinks=False,
        )
        executor = FileNodeExecutor(config)
        
        node = Node(
            name="read_file",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(symlink),
                format_type="txt",
            ),
        )
        
        result = await executor.execute(node, mock_context)
        assert not result.success
        assert "symlink" in result.error.lower()

    async def test_template_rendering_security(self, secure_executor, mock_context, temp_files):
        """Test that template rendering doesn't bypass security"""
        _, _, denied_dir = temp_files
        
        # Inject path traversal via template
        mock_context.inputs["evil_path"] = str(denied_dir / "secret.key")
        
        node = Node(
            name="read_file",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path="{{ inputs.evil_path }}",
                format_type="txt",
            ),
        )
        
        result = await secure_executor.execute(node, mock_context)
        assert not result.success
        assert "outside allowed directories" in result.error

    async def test_skip_errors_with_security(self, secure_executor, mock_context, temp_files):
        """Test skip_errors behavior with security violations"""
        base, allowed_dir, denied_dir = temp_files
        
        # Create pattern that would match files in both allowed and denied dirs
        # But since we're using a security config that only allows the allowed dir,
        # trying to access files outside will fail
        node = Node(
            name="read_files",
            type=NodeType.FILE,
            config=FileNodeConfig(
                pattern=str(allowed_dir / "*.txt"),  # Pattern within allowed dir
                format_type="txt",
                skip_errors=True,  # Should skip any errors
                merge=True,
            ),
        )
        
        # Add a file that matches denied pattern to test skip_errors
        (allowed_dir / "passwords.txt").write_text("should be skipped")
        
        # Use executor that only allows the allowed directory
        result = await secure_executor.execute(node, mock_context)
        
        # Should succeed with only allowed files (test.txt, not passwords.txt)
        assert result.success
        # With single txt file and merge=True, returns content directly
        assert result.output["data"] == "Hello World"

    async def test_file_size_limit(self, temp_files, mock_context):
        """Test file size limit enforcement"""
        _, allowed_dir, _ = temp_files
        
        # Create a large file
        large_file = allowed_dir / "large.dat"
        large_file.write_bytes(b"x" * 10000)
        
        # Executor with size limit
        config = FileSecurityConfig(
            allowed_base_dirs=[str(allowed_dir)],
            max_file_size=5000,  # 5KB limit
        )
        executor = FileNodeExecutor(config)
        
        node = Node(
            name="read_file",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(large_file),
                format_type="txt",
            ),
        )
        
        result = await executor.execute(node, mock_context)
        assert not result.success
        assert "exceeds maximum" in result.error

    async def test_extension_restrictions(self, temp_files, mock_context):
        """Test file extension restrictions"""
        _, allowed_dir, _ = temp_files
        
        # Create file with non-allowed extension
        (allowed_dir / "script.py").write_text("print('hello')")
        
        # Executor that only allows specific extensions
        config = FileSecurityConfig(
            allowed_base_dirs=[str(allowed_dir)],
            require_file_extensions=[".txt", ".json", ".csv"],
        )
        executor = FileNodeExecutor(config)
        
        # Should fail for .py file
        node = Node(
            name="read_file",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(allowed_dir / "script.py"),
                format_type="txt",
            ),
        )
        
        result = await executor.execute(node, mock_context)
        assert not result.success
        assert "extension" in result.error.lower()
        
        # Should work for allowed extension
        node_allowed = Node(
            name="read_file",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(allowed_dir / "test.txt"),
                format_type="txt",
            ),
        )
        
        result_allowed = await executor.execute(node_allowed, mock_context)
        assert result_allowed.success