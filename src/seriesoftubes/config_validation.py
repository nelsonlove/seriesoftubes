"""Configuration validation for security settings"""

import os
import sys
from typing import List


def validate_required_env_vars() -> None:
    """Validate that all required environment variables are set.
    
    Raises:
        SystemExit: If any required environment variables are missing
    """
    missing_vars: List[str] = []
    
    # Required security variables
    required_vars = {
        "JWT_SECRET_KEY": (
            "JWT secret key for token signing. "
            "Generate with: openssl rand -hex 32"
        ),
    }
    
    # At least one LLM API key is required
    llm_api_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    if not any(os.getenv(key) for key in llm_api_keys):
        missing_vars.append(
            "  - LLM API Key: At least one of OPENAI_API_KEY or ANTHROPIC_API_KEY must be set"
        )
    
    # Optional but recommended security variables
    recommended_vars = {
        "REDIS_URL": (
            "Redis connection URL with authentication. "
            "Example: redis://:password@localhost:6379"
        ),
        "DATABASE_URL": (
            "Database connection URL. "
            "For production, use PostgreSQL with SSL"
        ),
    }
    
    # Check required variables
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"  - {var}: {description}")
    
    if missing_vars:
        print("ERROR: Missing required environment variables:", file=sys.stderr)
        print("\n".join(missing_vars), file=sys.stderr)
        print("\nPlease set these variables before starting the application.", file=sys.stderr)
        sys.exit(1)
    
    # Check recommended variables and warn if missing
    missing_recommended = []
    for var, description in recommended_vars.items():
        if not os.getenv(var):
            missing_recommended.append(f"  - {var}: {description}")
    
    if missing_recommended:
        print("WARNING: Missing recommended environment variables:")
        print("\n".join(missing_recommended))
        print()


def validate_security_config() -> None:
    """Validate security configuration settings.
    
    Checks for common security misconfigurations and warns about them.
    """
    warnings = []
    
    # Check JWT secret strength
    jwt_secret = os.getenv("JWT_SECRET_KEY", "")
    if len(jwt_secret) < 32:
        warnings.append(
            "JWT_SECRET_KEY should be at least 32 characters long for security. "
            "Generate a secure key with: openssl rand -hex 32"
        )
    
    # Check Redis URL for authentication
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    if redis_url.startswith("redis://localhost") and "@" not in redis_url:
        warnings.append(
            "Redis is configured without authentication. "
            "Consider adding a password for production use."
        )
    
    # Check database URL for SSL
    db_url = os.getenv("DATABASE_URL", "")
    if db_url.startswith("postgresql://") and "sslmode=" not in db_url:
        warnings.append(
            "PostgreSQL connection does not specify SSL mode. "
            "Consider adding ?sslmode=require for production."
        )
    
    # Check API URL for HTTPS
    api_url = os.getenv("SERIESOFTUBES_API_URL", "")
    if api_url.startswith("http://") and "localhost" not in api_url:
        warnings.append(
            "API URL uses HTTP instead of HTTPS. "
            "Use HTTPS in production to protect credentials."
        )
    
    if warnings:
        print("SECURITY WARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")
        print()


def generate_secure_config_template() -> str:
    """Generate a template .env file with secure defaults.
    
    Returns:
        Template environment file content
    """
    import secrets
    
    return f"""# SeriesOfTubes Environment Configuration
# Generated secure configuration

# ===== REQUIRED SETTINGS =====

# JWT secret for authentication (auto-generated)
JWT_SECRET_KEY={secrets.token_hex(32)}

# LLM API Keys (set at least one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# ===== DATABASE =====

# For development (SQLite)
DATABASE_URL=sqlite+aiosqlite:///~/.seriesoftubes/db.sqlite

# For production (PostgreSQL with SSL)
# DATABASE_URL=postgresql://user:password@localhost:5432/seriesoftubes?sslmode=require

# ===== REDIS =====

# For development (no auth)
REDIS_URL=redis://localhost:6379

# For production (with auth)
# REDIS_URL=redis://:your-secure-password@localhost:6379/0

# ===== API CONFIGURATION =====

# API URL (use HTTPS in production)
SERIESOFTUBES_API_URL=http://localhost:8000

# CORS origins (update for production)
CORS_ORIGINS=http://localhost:3000

# ===== SECURITY SETTINGS =====

ACCESS_TOKEN_EXPIRE_MINUTES=30
BCRYPT_ROUNDS=12

# ===== OPTIONAL FEATURES =====

# File security
FILE_SECURITY_ENABLED=false
# FILE_SECURITY_ALLOWED_DIRS=["/data/workflows", "/data/uploads"]
# FILE_SECURITY_MAX_SIZE_MB=100

# Python node security
PYTHON_SECURITY_LEVEL=normal
PYTHON_EXECUTION_TIMEOUT=30

# ===== DEVELOPMENT =====

LOG_LEVEL=INFO
DEBUG=false
"""


if __name__ == "__main__":
    # Generate template if requested
    if len(sys.argv) > 1 and sys.argv[1] == "--generate-template":
        print(generate_secure_config_template())
        sys.exit(0)
    
    # Otherwise validate current configuration
    validate_required_env_vars()
    validate_security_config()
    print("Configuration validation passed ✓")