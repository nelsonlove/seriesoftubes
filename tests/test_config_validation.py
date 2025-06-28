"""Tests for configuration validation"""

import os
import pytest
from unittest.mock import patch

from seriesoftubes.config_validation import (
    validate_required_env_vars,
    validate_security_config,
    generate_secure_config_template,
)


class TestConfigValidation:
    """Test configuration validation functions"""

    def test_validate_required_env_vars_missing(self):
        """Test validation fails when JWT_SECRET_KEY is missing"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                validate_required_env_vars()
            assert exc_info.value.code == 1

    def test_validate_required_env_vars_present(self):
        """Test validation passes when all required vars are present"""
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "test-secret-key-123",
            "OPENAI_API_KEY": "sk-test-key"
        }):
            # Should not raise
            validate_required_env_vars()

    def test_validate_security_config_warnings(self, capsys):
        """Test security warnings are printed for weak configurations"""
        test_env = {
            "JWT_SECRET_KEY": "short",  # Too short
            "REDIS_URL": "redis://localhost:6379",  # No auth
            "DATABASE_URL": "postgresql://user:pass@host/db",  # No SSL
            "SERIESOFTUBES_API_URL": "http://api.example.com",  # HTTP not HTTPS
        }
        
        with patch.dict(os.environ, test_env):
            validate_security_config()
            
        captured = capsys.readouterr()
        assert "SECURITY WARNINGS:" in captured.out
        assert "JWT_SECRET_KEY should be at least 32 characters" in captured.out
        assert "Redis is configured without authentication" in captured.out
        assert "PostgreSQL connection does not specify SSL mode" in captured.out
        assert "API URL uses HTTP instead of HTTPS" in captured.out

    def test_validate_security_config_no_warnings(self, capsys):
        """Test no warnings for secure configuration"""
        test_env = {
            "JWT_SECRET_KEY": "a" * 32,  # Long enough
            "REDIS_URL": "redis://:password@localhost:6379",  # With auth
            "DATABASE_URL": "postgresql://user:pass@host/db?sslmode=require",  # With SSL
            "SERIESOFTUBES_API_URL": "https://api.example.com",  # HTTPS
        }
        
        with patch.dict(os.environ, test_env):
            validate_security_config()
            
        captured = capsys.readouterr()
        assert "SECURITY WARNINGS:" not in captured.out

    def test_validate_security_config_localhost_http_ok(self, capsys):
        """Test HTTP is OK for localhost"""
        test_env = {
            "JWT_SECRET_KEY": "a" * 32,
            "SERIESOFTUBES_API_URL": "http://localhost:8000",  # HTTP localhost is OK
        }
        
        with patch.dict(os.environ, test_env):
            validate_security_config()
            
        captured = capsys.readouterr()
        assert "API URL uses HTTP instead of HTTPS" not in captured.out

    def test_generate_secure_config_template(self):
        """Test secure config template generation"""
        template = generate_secure_config_template()
        
        # Check required sections are present
        assert "JWT_SECRET_KEY=" in template
        assert "REDIS_URL=" in template
        assert "DATABASE_URL=" in template
        assert "SERIESOFTUBES_API_URL=" in template
        
        # Check it includes security recommendations
        assert "sslmode=require" in template
        assert "your-secure-password" in template  # Redis password example
        assert "https://" in template or "HTTPS" in template  # HTTPS recommendation
        
        # Check JWT secret is actually generated (64 hex chars)
        import re
        jwt_match = re.search(r'JWT_SECRET_KEY=([a-f0-9]{64})', template)
        assert jwt_match is not None