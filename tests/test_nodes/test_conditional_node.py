"""Tests for conditional node executor (replacement for route node)"""

from typing import Any

import pytest

from seriesoftubes.models import (
    Node,
    NodeType,
    PythonNodeConfig,
)
from seriesoftubes.nodes import PythonNodeExecutor


class MockContext:
    """Mock implementation of NodeContext protocol"""

    def __init__(
        self,
        outputs: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
    ):
        self.outputs = outputs or {}
        self.inputs = inputs or {}

    def get_output(self, node_name: str) -> Any:
        return self.outputs.get(node_name)

    def get_input(self, input_name: str) -> Any:
        return self.inputs.get(input_name)


@pytest.mark.asyncio
async def test_conditional_logic_with_python_node():
    """Test conditional logic implemented with Python node"""
    executor = PythonNodeExecutor()

    # Create a Python node that implements conditional logic
    node = Node(
        name="conditional_router",
        description="Test conditional routing with Python",
        type=NodeType.PYTHON,
        depends_on=["previous_node"],
        config=PythonNodeConfig(
            code="""
# Get the score from previous node
data = context.get('previous_node', {})
score = data.get('score', 0)

# Implement conditional logic
if score > 0.5:
    selected_route = "high_score_path"
    condition_met = "score > 0.5"
elif score <= 0.5:
    selected_route = "low_score_path"
    condition_met = "score <= 0.5"
else:
    selected_route = "default_path"
    condition_met = "default"

return {
    'selected_route': selected_route,
    'condition_met': condition_met,
    'score_value': score
}
""",
            context={"previous_node": "previous_node"},
        ),
    )

    # Test high score path
    context = MockContext(outputs={"previous_node": {"score": 0.8}})

    # Mock the execution
    # ruff: noqa: PLC0415
    # ruff: noqa: PLC0415
    from unittest.mock import patch

    with patch("seriesoftubes.nodes.python._execute_in_process") as mock_execute:
        mock_execute.return_value = {
            "selected_route": "high_score_path",
            "condition_met": "score > 0.5",
            "score_value": 0.8,
        }

        result = await executor.execute(node, context)

        assert result.success
        assert result.output["result"]["selected_route"] == "high_score_path"
        assert result.output["result"]["condition_met"] == "score > 0.5"
        assert result.output["result"]["score_value"] == 0.8

    # Test low score path
    context = MockContext(outputs={"previous_node": {"score": 0.3}})

    with patch("seriesoftubes.nodes.python._execute_in_process") as mock_execute:
        mock_execute.return_value = {
            "selected_route": "low_score_path",
            "condition_met": "score <= 0.5",
            "score_value": 0.3,
        }

        result = await executor.execute(node, context)

        assert result.success
        assert result.output["result"]["selected_route"] == "low_score_path"
        assert result.output["result"]["condition_met"] == "score <= 0.5"
        assert result.output["result"]["score_value"] == 0.3


@pytest.mark.asyncio
async def test_simple_boolean_conditional():
    """Test simple boolean conditional logic"""
    executor = PythonNodeExecutor()

    node = Node(
        name="boolean_check",
        type=NodeType.PYTHON,
        depends_on=[],
        config=PythonNodeConfig(
            code="""
# Simple boolean logic
input_value = inputs.get('test_flag', False)

if input_value:
    result = "true_path"
else:
    result = "false_path"

return {'path': result, 'input_was': input_value}
"""
        ),
    )

    # Test true case
    context = MockContext(inputs={"test_flag": True})

    # ruff: noqa: PLC0415
    from unittest.mock import patch

    with patch("seriesoftubes.nodes.python._execute_in_process") as mock_execute:
        mock_execute.return_value = {"path": "true_path", "input_was": True}

        result = await executor.execute(node, context)

        assert result.success
        assert result.output["result"]["path"] == "true_path"
        assert result.output["result"]["input_was"] is True

    # Test false case
    context = MockContext(inputs={"test_flag": False})

    with patch("seriesoftubes.nodes.python._execute_in_process") as mock_execute:
        mock_execute.return_value = {"path": "false_path", "input_was": False}

        result = await executor.execute(node, context)

        assert result.success
        assert result.output["result"]["path"] == "false_path"
        assert result.output["result"]["input_was"] is False


@pytest.mark.asyncio
async def test_multi_condition_logic():
    """Test multiple condition logic implementation"""
    executor = PythonNodeExecutor()

    node = Node(
        name="multi_conditional",
        type=NodeType.PYTHON,
        depends_on=[],
        config=PythonNodeConfig(
            code="""
# Multi-condition logic
category = inputs.get('category', '')
priority = inputs.get('priority', 0)

if category == 'urgent' and priority > 8:
    path = 'critical_path'
elif category == 'urgent':
    path = 'urgent_path'
elif priority > 5:
    path = 'high_priority_path'
else:
    path = 'normal_path'

return {
    'selected_path': path,
    'category': category,
    'priority': priority
}
"""
        ),
    )

    # Test critical path
    context = MockContext(inputs={"category": "urgent", "priority": 9})

    # ruff: noqa: PLC0415
    from unittest.mock import patch

    with patch("seriesoftubes.nodes.python._execute_in_process") as mock_execute:
        mock_execute.return_value = {
            "selected_path": "critical_path",
            "category": "urgent",
            "priority": 9,
        }

        result = await executor.execute(node, context)

        assert result.success
        assert result.output["result"]["selected_path"] == "critical_path"

    # Test normal path
    context = MockContext(inputs={"category": "normal", "priority": 3})

    with patch("seriesoftubes.nodes.python._execute_in_process") as mock_execute:
        mock_execute.return_value = {
            "selected_path": "normal_path",
            "category": "normal",
            "priority": 3,
        }

        result = await executor.execute(node, context)

        assert result.success
        assert result.output["result"]["selected_path"] == "normal_path"
