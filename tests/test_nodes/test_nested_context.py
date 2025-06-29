"""Test nested context attribute access in nodes"""

import pytest

from seriesoftubes.models import LLMNodeConfig, Node, NodeType
from seriesoftubes.nodes.base import NodeExecutor, NodeResult


class MockContext:
    """Mock context for testing"""
    
    def __init__(self):
        self.outputs = {}
        self.inputs = {}
    
    def get_output(self, node_name: str):
        return self.outputs.get(node_name)
    
    def get_input(self, input_name: str):
        return self.inputs.get(input_name)


class TestNodeExecutor(NodeExecutor):
    """Test executor to test base class methods"""
    
    async def execute(self, node: Node, context) -> NodeResult:
        # Just return the prepared context data
        data = self.prepare_context_data(node, context)
        return NodeResult(output=data, success=True)


@pytest.mark.asyncio
async def test_nested_attribute_access():
    """Test accessing nested attributes in context mappings"""
    # Create test context with nested output
    context = MockContext()
    context.outputs["extract_profile"] = {
        "response": "User profile extracted",
        "structured_output": {
            "name": "John Doe",
            "location": "San Francisco",
            "skills": ["Python", "AI", "Machine Learning"]
        },
        "model_used": "gpt-4"
    }
    context.outputs["other_node"] = {"value": 42}
    
    # Create node with context mapping using nested attributes
    config = LLMNodeConfig(
        prompt="Test prompt",
        context={
            "profile": "extract_profile.structured_output",
            "location": "extract_profile.structured_output.location",
            "model": "extract_profile.model_used",
            "other": "other_node.value",
            "missing": "nonexistent.field",
            "deep_missing": "extract_profile.structured_output.nonexistent.field"
        }
    )
    node = Node(name="test_node", node_type=NodeType.LLM, config=config)
    
    # Execute test
    executor = TestNodeExecutor()
    result = await executor.execute(node, context)
    
    assert result.success is True
    data = result.output
    
    # Verify nested attribute access worked
    assert data["profile"] == {
        "name": "John Doe",
        "location": "San Francisco",
        "skills": ["Python", "AI", "Machine Learning"]
    }
    assert data["location"] == "San Francisco"
    assert data["model"] == "gpt-4"
    assert data["other"] == 42
    assert data["missing"] is None  # Nonexistent node
    assert data["deep_missing"] is None  # Nonexistent nested field


@pytest.mark.asyncio
async def test_simple_context_mapping():
    """Test simple context mapping without nested attributes"""
    # Create test context
    context = MockContext()
    context.outputs["node1"] = {"data": "value1"}
    context.outputs["node2"] = "simple string"
    
    # Create node with simple context mapping
    config = LLMNodeConfig(
        prompt="Test prompt",
        context={
            "data1": "node1",
            "data2": "node2"
        }
    )
    node = Node(name="test_node", node_type=NodeType.LLM, config=config)
    
    # Execute test
    executor = TestNodeExecutor()
    result = await executor.execute(node, context)
    
    assert result.success is True
    data = result.output
    
    # Verify simple mappings work
    assert data["data1"] == {"data": "value1"}
    assert data["data2"] == "simple string"


@pytest.mark.asyncio
async def test_mixed_attribute_types():
    """Test accessing attributes from different types of objects"""
    # Create test context with different output types
    context = MockContext()
    
    # Dict with nested dicts
    context.outputs["dict_node"] = {
        "level1": {
            "level2": {
                "value": "nested value"
            }
        }
    }
    
    # List access (should return None as we don't support index access)
    context.outputs["list_node"] = ["item1", "item2", "item3"]
    
    # None value
    context.outputs["none_node"] = None
    
    # Create node with various attribute accesses
    config = LLMNodeConfig(
        prompt="Test prompt",
        context={
            "nested": "dict_node.level1.level2.value",
            "list_item": "list_node.0",  # This won't work, should be None
            "none_attr": "none_node.field",  # Should be None
            "missing_deep": "dict_node.level1.missing.value"  # Should be None
        }
    )
    node = Node(name="test_node", node_type=NodeType.LLM, config=config)
    
    # Execute test
    executor = TestNodeExecutor()
    result = await executor.execute(node, context)
    
    assert result.success is True
    data = result.output
    
    # Verify results
    assert data["nested"] == "nested value"
    assert data["list_item"] is None  # We don't support index access
    assert data["none_attr"] is None
    assert data["missing_deep"] is None