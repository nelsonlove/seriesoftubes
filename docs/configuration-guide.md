# Configuration Guide

SeriesOfTubes uses a two-file configuration system to separate secrets from settings.

## Configuration Files

### 1. `.env` - Secrets and Environment Variables

Store all sensitive information here. This file should **never** be committed to git.

```bash
# API Keys (required - at least one)
OPENAI_API_KEY=sk-proj-abc123...
ANTHROPIC_API_KEY=sk-ant-api03-xyz789...

# Security (required)
JWT_SECRET_KEY=your-secret-key-here

# Database (optional - defaults to SQLite)
DATABASE_URL=postgresql://user:password@localhost:5432/seriesoftubes

# Redis (optional - defaults to memory cache)
REDIS_URL=redis://localhost:6379
```

### 2. `.tubes.yaml` - Workflow Settings

Non-sensitive configuration that can be version controlled.

```yaml
llm:
  provider: openai              # Which LLM to use
  model: gpt-4o                 # Model name
  api_key_env: OPENAI_API_KEY   # Which env var contains the key
  temperature: 0.7              # Model parameters
  max_tokens: 4096

cache:
  enabled: true
  backend: redis                # Use Redis if available
  ttl: 3600
```

## How They Work Together

1. **`.env` defines the secret**:
   ```
   OPENAI_API_KEY=sk-proj-abc123...
   ```

2. **`.tubes.yaml` references it**:
   ```yaml
   api_key_env: OPENAI_API_KEY
   ```

3. **The app reads the env var name from `.tubes.yaml`, then gets the actual value from the environment**

## Common Patterns

### Using Multiple LLM Providers

`.env`:
```bash
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
MY_CUSTOM_KEY=sk-custom-...
```

`.tubes.yaml`:
```yaml
llm:
  provider: openai
  api_key_env: OPENAI_API_KEY  # Can change to ANTHROPIC_API_KEY
```

### Environment-Specific Settings

`.env.development`:
```bash
DATABASE_URL=postgresql://dev:dev@localhost:5432/tubes_dev
LOG_LEVEL=DEBUG
```

`.env.production`:
```bash
DATABASE_URL=postgresql://prod:secure@db.example.com:5432/tubes
LOG_LEVEL=INFO
```

### Per-Workflow Overrides

Workflows can override the default LLM settings:

```yaml
# workflow.yaml
name: my-workflow
config:
  llm:
    model: gpt-4-turbo  # Override the default model
    temperature: 0.2    # More deterministic for this workflow
```

## Best Practices

1. **Never commit `.env`** - It's in `.gitignore` for a reason
2. **Use `.env.example`** - Show what variables are needed without values
3. **Keep `.tubes.yaml` generic** - Avoid environment-specific settings
4. **Use descriptive env var names** - `OPENAI_API_KEY` not `KEY1`
5. **Document required variables** - In README or `.env.example`

## Loading Order

1. Environment variables (highest priority)
2. `.env` file (loaded by python-dotenv)
3. `.tubes.yaml` configuration
4. Workflow-specific config
5. Default values (lowest priority)

## Troubleshooting

### "API key not found"
1. Check `.env` has the key: `OPENAI_API_KEY=sk-...`
2. Check `.tubes.yaml` references it: `api_key_env: OPENAI_API_KEY`
3. Ensure `.env` is in the project root
4. Restart the application after changing `.env`

### "Invalid configuration"
1. Validate YAML syntax: `yamllint .tubes.yaml`
2. Check for typos in env var names
3. Ensure all required fields are present

### Docker Considerations

When using Docker, pass environment variables explicitly:

```yaml
# docker-compose.yml
services:
  api:
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}  # From host .env
```

Or mount the `.env` file:

```yaml
volumes:
  - ./.env:/app/.env:ro
```