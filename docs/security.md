# Security Configuration Guide

This guide covers security best practices and configuration for SeriesOfTubes.

## Required Security Configuration

### JWT Secret Key

The `JWT_SECRET_KEY` environment variable is **required** and must be set before starting the application. This key is used to sign JWT tokens for authentication.

**Generate a secure secret:**
```bash
openssl rand -hex 32
```

**Set the environment variable:**
```bash
export JWT_SECRET_KEY="your-generated-secret-here"
```

⚠️ **Important**: 
- Never use default or example secrets in production
- The secret should be at least 32 characters long
- Keep this secret secure and never commit it to version control

## Configuration Setup

SeriesOfTubes uses a two-file configuration approach:
- `.env` - For secrets and sensitive configuration (never commit this)
- `.tubes.yaml` - For non-sensitive workflow settings (can be committed)

### Quick Setup

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API keys
# At minimum, set JWT_SECRET_KEY and one LLM API key
```

### Generate Secure Configuration

For production deployments, use the configuration generator:

```bash
python -m seriesoftubes.cli.generate_config
```

This creates a `.env` file with:
- A securely generated JWT secret
- Template configuration for Redis with authentication
- PostgreSQL configuration with SSL
- HTTPS API endpoints
- Security best practices

### Validate Configuration

Check your current configuration:

```bash
python -m seriesoftubes.config_validation
```

This will:
- Verify all required environment variables are set
- Warn about potential security issues
- Suggest improvements for production deployments

## Security Features

### 1. Template Sandboxing

SeriesOfTubes uses a secure template engine with multiple security levels:

- **INTERPOLATION_ONLY**: Simple variable substitution only (used for paths, URLs)
- **SAFE_EXPRESSIONS**: Variables + safe filters in sandboxed environment
- **SANDBOXED**: Full Jinja2 in SandboxedEnvironment
- **UNSAFE**: Full Jinja2 (logs warnings, use only when necessary)

Different node types use appropriate security levels:
- File paths: INTERPOLATION_ONLY
- HTTP URLs/headers: INTERPOLATION_ONLY  
- LLM prompts: SAFE_EXPRESSIONS

### 2. Python Node Security

Python nodes execute code with RestrictedPython and configurable security levels:

- **STRICT**: Minimal builtins, no imports
- **NORMAL**: Safe builtins, limited imports (math, json, datetime)
- **TRUSTED**: Extended features for data science (numpy, pandas)

Features:
- AST-based code validation
- Import whitelisting
- Controlled builtin access
- Execution timeouts

### 3. File Path Security

File operations include comprehensive security:

- **Path validation**: Prevents directory traversal attacks
- **Access control**: Whitelist allowed directories
- **Pattern filtering**: Block sensitive files (*.key, passwords.*)
- **Size limits**: Configurable file size restrictions
- **Audit logging**: Track all file access attempts

Example configuration:
```python
from seriesoftubes.file_security import FileSecurityConfig, SecureFilePath

config = FileSecurityConfig(
    allowed_directories=["/data/workflows", "/data/uploads"],
    denied_patterns=["*.key", "*.pem", "*password*"],
    max_file_size_mb=100
)

secure_file = SecureFilePath(config)
```

## Production Deployment

### Environment Variables

Essential security environment variables:

```bash
# Required
JWT_SECRET_KEY=<generated-secret>

# Recommended
REDIS_URL=redis://:password@redis:6379/0
DATABASE_URL=postgresql://user:pass@db:5432/seriesoftubes?sslmode=require
SERIESOFTUBES_API_URL=https://api.yourdomain.com

# Security settings
ACCESS_TOKEN_EXPIRE_MINUTES=30
BCRYPT_ROUNDS=12
```

### Redis Security

Configure Redis with authentication:

```bash
REDIS_URL=redis://:your-redis-password@localhost:6379/0
```

For Redis 6+, use ACL for fine-grained permissions.

### Database Security

Always use SSL for PostgreSQL connections:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
```

Consider using:
- `sslmode=verify-full` for certificate validation
- Separate read/write database users
- Connection pooling with secure settings

### HTTPS Configuration

Always use HTTPS in production:

1. Configure your reverse proxy (nginx, Apache) with SSL
2. Set secure headers:
   ```nginx
   add_header Strict-Transport-Security "max-age=31536000" always;
   add_header X-Content-Type-Options "nosniff" always;
   add_header X-Frame-Options "DENY" always;
   ```

### CORS Configuration

Configure CORS for your specific domains:

```python
CORS_ORIGINS = ["https://app.yourdomain.com"]
```

Never use `*` for CORS origins in production.

## Security Checklist

Before deploying to production:

- [ ] JWT_SECRET_KEY is set to a strong, unique value
- [ ] Redis has authentication enabled
- [ ] PostgreSQL uses SSL connections
- [ ] API uses HTTPS
- [ ] CORS is configured for specific origins
- [ ] File security is enabled with appropriate restrictions
- [ ] Python execution uses appropriate security levels
- [ ] All passwords are strong and unique
- [ ] Logs don't contain sensitive information
- [ ] Regular security updates are applied

## Reporting Security Issues

If you discover a security vulnerability, please report it to:
- Email: security@seriesoftubes.example.com
- Do not open public issues for security vulnerabilities

We appreciate responsible disclosure and will acknowledge your contribution.