"""Tests for route node executor"""

import pytest

from seriesoftubes.models import (
    Node,
    NodeType,
    RouteConfig,
    RouteNodeConfig,
)
from seriesoftubes.nodes import RouteNodeExecutor


class MockContext:
    """Mock implementation of NodeContext protocol"""

    def __init__(
        self,
        outputs: dict[str, any] | None = None,
        inputs: dict[str, any] | None = None,
    ):
        self.outputs = outputs or {}
        self.inputs = inputs or {}

    def get_output(self, node_name: str) -> any:
        return self.outputs.get(node_name)

    def get_input(self, input_name: str) -> any:
        return self.inputs.get(input_name)


@pytest.mark.asyncio
async def test_route_node_executor():
    """Test route node execution"""
    executor = RouteNodeExecutor()

    # Create a route node with conditions
    node = Node(
        name="decide_path",
        type=NodeType.ROUTE,
        depends_on=["previous_node"],
        config=RouteNodeConfig(
            context={"data": "previous_node"},
            routes=[
                RouteConfig(when="data.score > 0.5", to="high_score_path"),
                RouteConfig(when="data.score <= 0.5", to="low_score_path"),
                RouteConfig(default=True, to="default_path"),
            ],
        ),
    )

    # Test high score path
    context = MockContext(outputs={"previous_node": {"score": 0.8}})
    result = await executor.execute(node, context)

    assert result.success
    assert result.output == "high_score_path"
    assert result.metadata["condition"] == "data.score > 0.5"

    # Test low score path
    context = MockContext(outputs={"previous_node": {"score": 0.3}})
    result = await executor.execute(node, context)

    assert result.success
    assert result.output == "low_score_path"
    assert result.metadata["condition"] == "data.score <= 0.5"


@pytest.mark.asyncio
async def test_route_node_default():
    """Test route node with default path"""
    executor = RouteNodeExecutor()

    node = Node(
        name="router",
        type=NodeType.ROUTE,
        depends_on=[],
        config=RouteNodeConfig(
            routes=[
                RouteConfig(when="false", to="never_selected"),
                RouteConfig(default=True, to="default_path"),
            ],
        ),
    )

    context = MockContext()
    result = await executor.execute(node, context)

    assert result.success
    assert result.output == "default_path"
    assert result.metadata["condition"] == "default"
