"""Tests for file security module"""

import os
import tempfile
from pathlib import Path

import pytest

from seriesoftubes.file_security import (
    AccessDeniedError,
    FileAccessError,
    FileAccessMode,
    FileSecurityConfig,
    PathTraversalError,
    SecureFilePath,
    validate_file_path,
)


class TestFileSecurityValidation:
    """Test file path validation and security checks"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some test files
            base = Path(tmpdir)
            (base / "allowed").mkdir()
            (base / "allowed" / "test.txt").write_text("test content")
            (base / "allowed" / "data.json").write_text('{"key": "value"}')
            (base / "denied").mkdir()
            (base / "denied" / "secret.key").write_text("secret")
            yield base

    @pytest.fixture
    def security_config(self, temp_dir):
        """Create security config for testing"""
        return FileSecurityConfig(
            allowed_base_dirs=[str(temp_dir / "allowed")],
            allow_symlinks=False,
        )

    def test_valid_path_access(self, temp_dir, security_config):
        """Test accessing valid paths"""
        security = SecureFilePath(security_config)
        
        # Valid file access
        path = security.validate_path(
            temp_dir / "allowed" / "test.txt",
            mode=FileAccessMode.READ
        )
        assert path.exists()
        assert path.name == "test.txt"

    def test_path_traversal_detection(self, temp_dir, security_config):
        """Test path traversal attack detection"""
        security = SecureFilePath(security_config)
        
        # Direct .. in path
        with pytest.raises(PathTraversalError):
            security.validate_path(
                temp_dir / "allowed" / ".." / "denied" / "secret.key"
            )
        
        # Encoded traversal
        with pytest.raises(PathTraversalError):
            security.validate_path("../etc/passwd")
        
        # Various traversal patterns
        traversal_attempts = [
            "../../etc/passwd",
            "allowed/../../../etc/passwd",
            "allowed/subdir/../../denied/secret.key",
            "./../denied/secret.key",
        ]
        
        for attempt in traversal_attempts:
            with pytest.raises(PathTraversalError):
                security.validate_path(attempt)

    def test_access_outside_allowed_dirs(self, temp_dir, security_config):
        """Test that access outside allowed directories is blocked"""
        security = SecureFilePath(security_config)
        
        # Try to access denied directory
        with pytest.raises(AccessDeniedError):
            security.validate_path(
                temp_dir / "denied" / "secret.key"
            )
        
        # Try to access parent directory
        with pytest.raises(AccessDeniedError):
            security.validate_path(temp_dir / "test.txt", must_exist=False)

    def test_denied_patterns(self, temp_dir):
        """Test denied file patterns"""
        # Create config that allows the directory but has denied patterns
        config = FileSecurityConfig(
            allowed_base_dirs=[str(temp_dir)],
            denied_patterns=["*.key", "*.secret", "*password*"],
        )
        security = SecureFilePath(config)
        
        # Allowed file
        path = security.validate_path(
            temp_dir / "allowed" / "test.txt"
        )
        assert path.exists()
        
        # Denied by pattern
        with pytest.raises(AccessDeniedError):
            security.validate_path(
                temp_dir / "denied" / "secret.key"
            )

    def test_file_extension_requirements(self, temp_dir):
        """Test file extension restrictions"""
        config = FileSecurityConfig(
            allowed_base_dirs=[str(temp_dir / "allowed")],
            require_file_extensions=[".txt", ".json"],
        )
        security = SecureFilePath(config)
        
        # Allowed extensions
        security.validate_path(temp_dir / "allowed" / "test.txt")
        security.validate_path(temp_dir / "allowed" / "data.json")
        
        # Create a file with disallowed extension
        (temp_dir / "allowed" / "script.py").write_text("print('hello')")
        
        # Should fail for disallowed extension
        with pytest.raises(FileAccessError):
            security.validate_path(
                temp_dir / "allowed" / "script.py",
                mode=FileAccessMode.READ
            )

    def test_symlink_handling(self, temp_dir):
        """Test symlink security"""
        if os.name == 'nt':  # Windows
            pytest.skip("Symlink test requires Unix-like OS")
        
        # Create a symlink
        allowed_dir = temp_dir / "allowed"
        target_file = temp_dir / "denied" / "secret.key"
        symlink = allowed_dir / "sneaky_link"
        symlink.symlink_to(target_file)
        
        # Config that disallows symlinks
        config = FileSecurityConfig(
            allowed_base_dirs=[str(allowed_dir)],
            allow_symlinks=False,
        )
        security = SecureFilePath(config)
        
        # Should fail with symlinks disabled
        with pytest.raises(FileAccessError):
            security.validate_path(symlink)
        
        # Config that allows symlinks (but still checks resolved path)
        config_with_symlinks = FileSecurityConfig(
            allowed_base_dirs=[str(allowed_dir)],
            allow_symlinks=True,
        )
        security_with_symlinks = SecureFilePath(config_with_symlinks)
        
        # Should still fail because resolved path is outside allowed dirs
        with pytest.raises(AccessDeniedError):
            security_with_symlinks.validate_path(symlink)

    def test_file_size_limits(self, temp_dir):
        """Test file size limit enforcement"""
        # Create a large file
        large_file = temp_dir / "allowed" / "large.dat"
        large_file.write_bytes(b"x" * 1000)
        
        # Config with size limit
        config = FileSecurityConfig(
            allowed_base_dirs=[str(temp_dir / "allowed")],
            max_file_size=500,  # 500 bytes
        )
        security = SecureFilePath(config)
        
        # Should fail for oversized file
        with pytest.raises(FileAccessError) as exc_info:
            security.validate_path(large_file, mode=FileAccessMode.READ)
        assert "exceeds maximum" in str(exc_info.value)
        
        # Small file should work
        small_file = temp_dir / "allowed" / "test.txt"
        security.validate_path(small_file, mode=FileAccessMode.READ)

    def test_write_permissions(self, temp_dir, security_config):
        """Test write/delete permission checks"""
        security = SecureFilePath(security_config)
        
        # Test write to existing file
        existing_file = temp_dir / "allowed" / "test.txt"
        path = security.validate_path(
            existing_file,
            mode=FileAccessMode.WRITE
        )
        assert path == existing_file.resolve()
        
        # Test write to new file
        new_file = temp_dir / "allowed" / "new.txt"
        path = security.validate_path(
            new_file,
            mode=FileAccessMode.WRITE,
            must_exist=False
        )
        assert path == new_file.resolve()
        
        # Test write to non-existent parent directory
        with pytest.raises(FileAccessError):
            security.validate_path(
                temp_dir / "allowed" / "nonexistent" / "file.txt",
                mode=FileAccessMode.WRITE,
                must_exist=False
            )

    def test_safe_join(self, temp_dir, security_config):
        """Test safe path joining"""
        security = SecureFilePath(security_config)
        
        # Valid join
        base = temp_dir / "allowed"
        joined = security.safe_join(base, "subdir", "file.txt")
        assert joined == (base / "subdir" / "file.txt").resolve()
        
        # Invalid joins with traversal
        with pytest.raises(PathTraversalError):
            security.safe_join(base, "..", "denied")
        
        with pytest.raises(PathTraversalError):
            security.safe_join(base, "subdir", "../..", "etc")
        
        with pytest.raises(PathTraversalError):
            security.safe_join(base, "/etc/passwd")

    def test_convenience_function(self, temp_dir):
        """Test the convenience validate_file_path function"""
        config = FileSecurityConfig(
            allowed_base_dirs=[str(temp_dir / "allowed")]
        )
        
        # Should work with valid path
        path = validate_file_path(
            temp_dir / "allowed" / "test.txt",
            config=config
        )
        assert path.exists()
        
        # Should fail with invalid path
        with pytest.raises(AccessDeniedError):
            validate_file_path(
                temp_dir / "denied" / "secret.key",
                config=config
            )

    def test_default_security_config(self):
        """Test default security configuration"""
        security = SecureFilePath()
        
        # Should only allow current directory by default
        cwd = Path.cwd()
        
        # Create a test file in current directory
        test_file = cwd / "test_temp.txt"
        test_file.write_text("test")
        
        try:
            # Should work for current directory
            path = security.validate_path(test_file)
            assert path == test_file.resolve()
            
            # Should fail for parent directory
            with pytest.raises(AccessDeniedError):
                security.validate_path(cwd.parent / "file.txt", must_exist=False)
        finally:
            # Clean up
            test_file.unlink(missing_ok=True)

    def test_case_sensitivity(self, temp_dir):
        """Test case sensitivity in security checks"""
        config = FileSecurityConfig(
            allowed_base_dirs=[str(temp_dir / "allowed")],
            denied_patterns=["*.KEY", "*.Secret"],  # Different case
        )
        security = SecureFilePath(config)
        
        # Create test file with lowercase extension
        (temp_dir / "allowed" / "test.key").write_text("key")
        
        # Should be blocked regardless of case in pattern
        with pytest.raises(AccessDeniedError):
            security.validate_path(temp_dir / "allowed" / "test.key")

    def test_url_encoded_traversal(self, security_config):
        """Test URL-encoded path traversal attempts"""
        security = SecureFilePath(security_config)
        
        # URL encoded traversal attempts
        encoded_attempts = [
            "%2e%2e/etc/passwd",
            "%252e%252e/etc/passwd",
            "..%2f..%2fetc%2fpasswd",
        ]
        
        for attempt in encoded_attempts:
            with pytest.raises(PathTraversalError):
                security.validate_path(attempt)