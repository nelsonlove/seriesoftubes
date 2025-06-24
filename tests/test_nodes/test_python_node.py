"""Tests for Python node executor"""

import tempfile
from pathlib import Path

import pytest

from seriesoftubes.models import Node, NodeType, PythonNodeConfig
from seriesoftubes.nodes.python import PythonNodeExecutor


class MockContext:
    """Mock implementation of NodeContext for testing"""

    def __init__(self, inputs=None, outputs=None):
        self.inputs = inputs or {}
        self.outputs = outputs or {}

    def get_output(self, node_name: str):
        return self.outputs.get(node_name)

    def get_input(self, input_name: str):
        return self.inputs.get(input_name)


@pytest.fixture
def executor():
    """Create a Python node executor"""
    return PythonNodeExecutor()


@pytest.fixture
def basic_context():
    """Create a basic node context"""
    return MockContext(
        inputs={"company": "Acme Corp", "year": 2024},
        outputs={"fetch_data": {"revenue": 1000000, "employees": 50}},
    )


@pytest.mark.asyncio
class TestPythonNodeBasics:
    """Test basic Python node functionality"""

    async def test_simple_inline_code(self, executor, basic_context):
        """Test executing simple inline Python code"""
        node = Node(
            name="process",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(
                code="""
# Simple calculation
result = context['inputs']['year'] + 10
return result
"""
            ),
        )

        result = await executor.execute(node, basic_context)
        assert result.success
        assert result.output == 2034

    async def test_complex_data_processing(self, executor, basic_context):
        """Test complex data processing with context"""
        node = Node(
            name="analyze",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(
                code="""
# Access data from previous nodes
data = context['fetch_data']
company = context['inputs']['company']

# Process the data
high_value = data['revenue'] > 500000
size = 'large' if data['employees'] > 100 else 'small'

return {
    'company': company,
    'high_value': high_value,
    'size': size,
    'score': data['revenue'] / data['employees']
}
""",
                context={"fetch_data": "fetch_data"},
            ),
        )

        result = await executor.execute(node, basic_context)
        assert result.success
        assert result.output["company"] == "Acme Corp"
        assert result.output["high_value"] is True
        assert result.output["size"] == "small"
        assert result.output["score"] == 20000

    async def test_list_comprehension(self, executor):
        """Test Python list comprehensions"""
        context = MockContext(
            inputs={},
            outputs={
                "items": [
                    {"name": "A", "value": 100},
                    {"name": "B", "value": 200},
                    {"name": "C", "value": 50},
                ]
            },
        )

        node = Node(
            name="filter",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(
                code="""
items = context['items']
filtered = [item for item in items if item['value'] > 75]
return {
    'count': len(filtered),
    'items': filtered,
    'total': sum(item['value'] for item in filtered)
}
""",
                context={"items": "items"},
            ),
        )

        result = await executor.execute(node, context)
        assert result.success
        assert result.output["count"] == 2
        assert result.output["total"] == 300

    async def test_file_based_code(self, executor, basic_context):
        """Test executing code from a file"""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
def analyze_company():
    company = context['inputs']['company']
    year = context['inputs']['year']

    return {
        'message': f"Analysis for {company} in {year}",
        'next_year': year + 1
    }
"""
            )
            temp_file = f.name

        try:
            node = Node(
                name="analyze",
                type=NodeType.PYTHON,
                config=PythonNodeConfig(file=temp_file, function="analyze_company"),
            )

            result = await executor.execute(node, basic_context)
            assert result.success
            assert result.output["message"] == "Analysis for Acme Corp in 2024"
            assert result.output["next_year"] == 2025
        finally:
            Path(temp_file).unlink()

    async def test_no_return_value(self, executor, basic_context):
        """Test code that modifies context without explicit return"""
        node = Node(
            name="modify",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(
                code="""
# Modify result in context
result = {
    'processed': True,
    'company': context['inputs']['company'].upper()
}
""",
            ),
        )

        result = await executor.execute(node, basic_context)
        assert result.success
        # Should return the modified context
        assert result.output["processed"] is True
        assert result.output["company"] == "ACME CORP"


@pytest.mark.asyncio
class TestPythonNodeSecurity:
    """Test security restrictions"""

    async def test_forbidden_builtins(self, executor, basic_context):
        """Test that dangerous builtins are blocked"""
        forbidden_code = [
            "exec('print(1)')",
            "eval('1+1')",
            "__import__('os')",
            "open('/etc/passwd')",
            "compile('1+1', '', 'eval')",
        ]

        for code in forbidden_code:
            node = Node(
                name="dangerous",
                type=NodeType.PYTHON,
                config=PythonNodeConfig(code=f"result = {code}"),
            )

            result = await executor.execute(node, basic_context)
            assert not result.success
            # The error should indicate the function is not available (blocked)
            assert (
                "not defined" in result.error.lower()
                or "not allowed" in result.error.lower()
                or "not found" in result.error.lower()
            )

    async def test_module_access_blocked(self, executor, basic_context):
        """Test that module access is blocked by default"""
        node = Node(
            name="module",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(code="import os\nresult = os.getcwd()"),
        )

        result = await executor.execute(node, basic_context)
        assert not result.success

    async def test_allowed_imports(self, executor, basic_context):
        """Test that explicitly allowed imports work"""
        node = Node(
            name="math",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(
                code="""
import math
result = {
    'pi': math.pi,
    'sqrt': math.sqrt(16)
}
return result
""",
                allowed_imports=["math"],
            ),
        )

        result = await executor.execute(node, basic_context)
        assert result.success
        assert result.output["pi"] == pytest.approx(3.14159, rel=1e-5)
        assert result.output["sqrt"] == 4.0

    async def test_timeout(self, executor, basic_context):
        """Test execution timeout"""
        node = Node(
            name="slow",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(
                code="""
# Simulate slow operation
import time
time.sleep(5)  # Sleep for 5 seconds
result = "done"
return result
""",
                timeout=1,  # 1 second timeout
                allowed_imports=["time"],
            ),
        )

        result = await executor.execute(node, basic_context)
        assert not result.success
        assert "timed out" in result.error.lower()

    async def test_output_size_limit(self, executor, basic_context):
        """Test output size limits"""
        node = Node(
            name="large",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(
                code="""
# Generate large output
result = ['x' * 1000 for _ in range(100)]
return result
""",
                max_output_size=1000,  # Very small limit
            ),
        )

        result = await executor.execute(node, basic_context)
        assert not result.success
        assert "exceeds limit" in result.error


@pytest.mark.asyncio
class TestPythonNodeValidation:
    """Test config validation"""

    async def test_missing_code_and_file(self):
        """Test that either code or file is required"""
        with pytest.raises(ValueError, match="Either 'code' or 'file'"):
            PythonNodeConfig()

    async def test_both_code_and_file(self):
        """Test that both code and file cannot be specified"""
        with pytest.raises(ValueError, match="Cannot specify both"):
            PythonNodeConfig(code="print(1)", file="test.py")

    async def test_invalid_syntax(self, executor, basic_context):
        """Test handling of invalid Python syntax"""
        node = Node(
            name="invalid",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(code="def invalid syntax"),
        )

        result = await executor.execute(node, basic_context)
        assert not result.success
        assert "Invalid Python syntax" in result.error

    async def test_file_not_found(self, executor, basic_context):
        """Test handling of missing files"""
        node = Node(
            name="missing",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(file="/nonexistent/file.py"),
        )

        result = await executor.execute(node, basic_context)
        assert not result.success
        assert "not found" in result.error


@pytest.mark.asyncio
class TestPythonNodeIntegration:
    """Test integration scenarios"""

    async def test_data_transformation_pipeline(self, executor):
        """Test a multi-step data transformation"""
        # First node output
        context = MockContext(
            inputs={"threshold": 100},
            outputs={
                "fetch": [
                    {"id": 1, "value": 150, "category": "A"},
                    {"id": 2, "value": 80, "category": "B"},
                    {"id": 3, "value": 200, "category": "A"},
                    {"id": 4, "value": 90, "category": "C"},
                ]
            },
        )

        node = Node(
            name="transform",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(
                code="""
# Complex data transformation
data = context['data']
threshold = context['inputs']['threshold']

# Filter and group
above_threshold = [d for d in data if d['value'] > threshold]

# Group by category
grouped = {}
for item in above_threshold:
    cat = item['category']
    if cat not in grouped:
        grouped[cat] = []
    grouped[cat].append(item)

# Calculate statistics
stats = {}
for cat, items in grouped.items():
    values = [i['value'] for i in items]
    stats[cat] = {
        'count': len(items),
        'total': sum(values),
        'average': sum(values) / len(values) if values else 0
    }

return {
    'filtered_count': len(above_threshold),
    'categories': list(grouped.keys()),
    'statistics': stats,
    'top_item': max(above_threshold, key=lambda x: x['value'])
}
""",
                context={"data": "fetch"},
            ),
        )

        result = await executor.execute(node, context)
        assert result.success
        assert result.output["filtered_count"] == 2
        assert set(result.output["categories"]) == {"A"}
        assert result.output["statistics"]["A"]["count"] == 2
        assert result.output["statistics"]["A"]["average"] == 175
        assert result.output["top_item"]["id"] == 3

    async def test_json_manipulation(self, executor, basic_context):
        """Test JSON serialization capabilities"""
        node = Node(
            name="json_ops",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(
                code="""
# JSON is always available
data = {
    'nested': {
        'array': [1, 2, 3],
        'string': 'test'
    }
}

# Serialize and deserialize
json_str = json.dumps(data)
parsed = json.loads(json_str)

return {
    'original': data,
    'serialized_length': len(json_str),
    'roundtrip_success': data == parsed
}
""",
            ),
        )

        result = await executor.execute(node, basic_context)
        assert result.success
        assert result.output["roundtrip_success"] is True
