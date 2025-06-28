"""File security module for path validation and access control.

This module provides secure file path handling to prevent path traversal
attacks and enforce file access policies.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Optional, Union


class FileAccessError(Exception):
    """Raised when file access is denied for security reasons"""
    pass


class PathTraversalError(FileAccessError):
    """Raised when path traversal is detected"""
    pass


class AccessDeniedError(FileAccessError):
    """Raised when accessing a file outside allowed directories"""
    pass


class FileAccessMode(str, Enum):
    """File access modes for security policies"""
    
    READ = "read"
    WRITE = "write"
    DELETE = "delete"


class FileSecurityConfig:
    """Configuration for file security policies"""
    
    def __init__(
        self,
        allowed_base_dirs: Optional[list[str]] = None,
        denied_patterns: Optional[list[str]] = None,
        allow_symlinks: bool = False,
        require_file_extensions: Optional[list[str]] = None,
        max_file_size: Optional[int] = None,
    ):
        """Initialize file security configuration.
        
        Args:
            allowed_base_dirs: List of allowed base directories (None = current dir only)
            denied_patterns: List of glob patterns for denied files
            allow_symlinks: Whether to allow following symlinks
            require_file_extensions: If set, only these extensions are allowed
            max_file_size: Maximum file size in bytes (for read operations)
        """
        self.allowed_base_dirs = allowed_base_dirs or [os.getcwd()]
        self.denied_patterns = denied_patterns or [
            "*.key", "*.pem", "*.env", ".env*", "*.secret",
            "*password*", "*token*", "*credential*",
        ]
        self.allow_symlinks = allow_symlinks
        self.require_file_extensions = require_file_extensions
        self.max_file_size = max_file_size
        
        # Normalize and resolve allowed directories
        self.allowed_base_dirs = [
            Path(d).resolve() for d in self.allowed_base_dirs
        ]


class SecureFilePath:
    """Secure file path handler with validation and normalization"""
    
    def __init__(self, config: Optional[FileSecurityConfig] = None):
        """Initialize with security configuration.
        
        Args:
            config: Security configuration (uses defaults if None)
        """
        self.config = config or FileSecurityConfig()
    
    def validate_path(
        self,
        path: Union[str, Path],
        mode: FileAccessMode = FileAccessMode.READ,
        must_exist: bool = True,
    ) -> Path:
        """Validate and normalize a file path.
        
        Args:
            path: Path to validate
            mode: Access mode (read/write/delete)
            must_exist: Whether the file must exist
            
        Returns:
            Normalized absolute path
            
        Raises:
            PathTraversalError: If path traversal is detected
            AccessDeniedError: If path is outside allowed directories
            FileNotFoundError: If must_exist=True and file doesn't exist
            FileAccessError: For other security violations
        """
        # First check the raw string for encoded traversal attempts
        if isinstance(path, str):
            self._check_encoded_traversal(path)
        
        # Convert to Path object
        path_obj = Path(path)
        
        # Check for path traversal attempts
        self._check_path_traversal(path_obj)
        
        # Resolve to absolute path (follows symlinks)
        try:
            if must_exist or path_obj.exists():
                resolved_path = path_obj.resolve()
            else:
                # For non-existent files, resolve the parent and join the name
                parent = path_obj.parent.resolve()
                resolved_path = parent / path_obj.name
        except (OSError, RuntimeError) as e:
            raise FileAccessError(f"Failed to resolve path: {e}")
        
        # Check symlink policy
        if not self.config.allow_symlinks and path_obj.exists() and path_obj.is_symlink():
            raise FileAccessError(f"Symlinks are not allowed: {path}")
        
        # Verify path is within allowed directories
        if not self._is_path_allowed(resolved_path):
            raise AccessDeniedError(
                f"Path '{path}' is outside allowed directories"
            )
        
        # Check file extension if required
        if mode == FileAccessMode.READ and self.config.require_file_extensions:
            if resolved_path.suffix.lower() not in self.config.require_file_extensions:
                raise FileAccessError(
                    f"File extension '{resolved_path.suffix}' is not allowed"
                )
        
        # Check against denied patterns
        if self._matches_denied_pattern(resolved_path):
            raise AccessDeniedError(
                f"File '{resolved_path.name}' matches a denied pattern"
            )
        
        # Check file exists if required
        if must_exist and not resolved_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        # Check file size for read operations
        if (
            mode == FileAccessMode.READ
            and resolved_path.exists()
            and resolved_path.is_file()
            and self.config.max_file_size is not None
        ):
            file_size = resolved_path.stat().st_size
            if file_size > self.config.max_file_size:
                raise FileAccessError(
                    f"File size ({file_size} bytes) exceeds maximum "
                    f"allowed size ({self.config.max_file_size} bytes)"
                )
        
        # Additional checks for write/delete operations
        if mode in (FileAccessMode.WRITE, FileAccessMode.DELETE):
            if resolved_path.exists() and not os.access(resolved_path, os.W_OK):
                raise FileAccessError(f"No write permission for: {path}")
            elif not resolved_path.parent.exists():
                raise FileAccessError(f"Parent directory does not exist: {path}")
            elif not os.access(resolved_path.parent, os.W_OK):
                raise FileAccessError(f"No write permission for parent directory: {path}")
        
        return resolved_path
    
    def _check_encoded_traversal(self, path_str: str) -> None:
        """Check for encoded path traversal attempts.
        
        Args:
            path_str: Raw path string to check
            
        Raises:
            PathTraversalError: If encoded traversal is detected
        """
        # Check for URL encoded traversal patterns
        encoded_patterns = [
            "%2e%2e",  # URL encoded ..
            "%252e%252e",  # Double encoded ..
            "%2f",  # URL encoded /
            "%5c",  # URL encoded \
            "%252f",  # Double encoded /
            "%255c",  # Double encoded \
        ]
        
        path_lower = path_str.lower()
        for pattern in encoded_patterns:
            if pattern in path_lower:
                raise PathTraversalError(
                    f"URL-encoded path traversal detected: '{pattern}' in '{path_str}'"
                )
    
    def _check_path_traversal(self, path: Path) -> None:
        """Check for path traversal attempts.
        
        Args:
            path: Path to check
            
        Raises:
            PathTraversalError: If path traversal is detected
        """
        # Check for .. segments
        if ".." in path.parts:
            raise PathTraversalError(
                f"Path traversal detected: '..' in path '{path}'"
            )
        
        # Check for absolute path indicators in string representation
        path_str = str(path)
        suspicious_patterns = [
            "../",
            "..\\",
            "/..",
            "\\..",
            "%2e%2e",  # URL encoded ..
            "%252e%252e",  # Double encoded ..
        ]
        
        for pattern in suspicious_patterns:
            if pattern.lower() in path_str.lower():
                raise PathTraversalError(
                    f"Path traversal pattern detected: '{pattern}' in '{path}'"
                )
    
    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is within allowed directories.
        
        Args:
            path: Resolved absolute path to check
            
        Returns:
            True if path is allowed
        """
        # Check if path is under any allowed base directory
        for allowed_dir in self.config.allowed_base_dirs:
            try:
                # This will raise ValueError if path is not relative to allowed_dir
                path.relative_to(allowed_dir)
                return True
            except ValueError:
                continue
        
        return False
    
    def _matches_denied_pattern(self, path: Path) -> bool:
        """Check if path matches any denied pattern.
        
        Args:
            path: Path to check
            
        Returns:
            True if path matches a denied pattern
        """
        path_str = str(path).lower()
        for pattern in self.config.denied_patterns:
            # Convert pattern to lowercase for case-insensitive matching
            pattern_lower = pattern.lower()
            # Use pathlib's match with lowercase strings
            if Path(path_str).match(pattern_lower):
                return True
        return False
    
    def safe_join(self, base: Union[str, Path], *parts: str) -> Path:
        """Safely join path components.
        
        Args:
            base: Base path
            *parts: Path components to join
            
        Returns:
            Joined and validated path
            
        Raises:
            PathTraversalError: If resulting path would escape base
        """
        base_path = Path(base).resolve()
        
        # Join parts
        joined = base_path
        for part in parts:
            # Check each part for traversal attempts
            if ".." in part or part.startswith("/") or part.startswith("\\"):
                raise PathTraversalError(
                    f"Invalid path component: '{part}'"
                )
            joined = joined / part
        
        # Validate the result
        return self.validate_path(joined, must_exist=False)


# Global instance for convenience
_default_file_security = None


def get_file_security(config: Optional[FileSecurityConfig] = None) -> SecureFilePath:
    """Get file security handler instance.
    
    Args:
        config: Optional configuration (uses default if None)
        
    Returns:
        SecureFilePath instance
    """
    global _default_file_security
    
    if config is not None:
        return SecureFilePath(config)
    
    if _default_file_security is None:
        _default_file_security = SecureFilePath()
    
    return _default_file_security


def validate_file_path(
    path: Union[str, Path],
    mode: FileAccessMode = FileAccessMode.READ,
    config: Optional[FileSecurityConfig] = None,
) -> Path:
    """Convenience function to validate a file path.
    
    Args:
        path: Path to validate
        mode: Access mode
        config: Optional security configuration
        
    Returns:
        Validated path
    """
    security = get_file_security(config)
    return security.validate_path(path, mode)