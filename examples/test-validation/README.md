# Schema Validation Test Examples

This directory contains example workflows that demonstrate SeriesOfTubes' schema validation capabilities.

## Files

### validation-test.yaml
A workflow designed to trigger various validation errors. Use this to test that validation is working correctly:

```bash
# This will fail at various nodes due to validation errors
s10s run validation-test.yaml
```

Expected validation errors:
- `invalid_url_test`: URL must start with http:// or https://
- `empty_path_test`: Path cannot be empty
- `invalid_python`: datetime objects are not JSON-serializable

### valid-workflow.yaml
A properly structured workflow that passes all validation:

```bash
# This should run successfully (assuming templates/analysis.txt exists)
s10s run valid-workflow.yaml --inputs company_name="Acme Corp"
```

## Testing Validation

### 1. Test Invalid URL
```bash
s10s run validation-test.yaml --inputs invalid_url="ftp://example.com"
```

### 2. Test Empty Environment Variable
```bash
unset API_KEY
s10s run valid-workflow.yaml --inputs company_name="Test Corp"
```

### 3. Test Missing Required Input
```bash
s10s run valid-workflow.yaml  # Missing required company_name
```

## What to Look For

When validation fails, you should see clear error messages like:

```
Input validation failed for node 'api_call':
  - url: Value error, URL must start with http:// or https://
```

This is much better than cryptic runtime errors or silent failures!

## Creating Validation Tests

To test validation in your own workflows:

1. **Test empty values**: Use undefined variables that render to empty strings
2. **Test type mismatches**: Pass strings where numbers are expected
3. **Test format validation**: Use invalid URLs, paths, etc.
4. **Test serialization**: Return non-JSON types from Python nodes

Remember: Good validation helps catch errors early and makes debugging much easier!
