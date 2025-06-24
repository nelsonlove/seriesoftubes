"""Tests for parallel execution of workflow nodes"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from seriesoftubes.engine import WorkflowEngine
from seriesoftubes.models import HTTPNodeConfig, Node, NodeType, Workflow
from seriesoftubes.nodes import NodeResult


class SlowHTTPNodeExecutor:
    """Mock HTTP executor that simulates slow API calls"""

    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.call_times = {}

    async def execute(self, node: Node, context) -> NodeResult:  # noqa: ARG002
        """Execute with a delay to simulate network latency"""
        start_time = time.time()
        await asyncio.sleep(self.delay)
        self.call_times[node.name] = {"start": start_time, "end": time.time()}
        return NodeResult(
            output={"data": f"Response from {node.name}"},
            success=True,
        )


@pytest.mark.asyncio
async def test_parallel_execution_of_independent_nodes():
    """Test that independent nodes execute in parallel"""
    # Create a workflow with two independent nodes and one dependent node
    workflow = Workflow(
        name="parallel-test",
        version="1.0.0",
        inputs={},
        nodes={
            "fetch_data_1": Node(
                name="fetch_data_1",
                type=NodeType.HTTP,
                depends_on=[],
                config=HTTPNodeConfig(url="https://api1.example.com"),
            ),
            "fetch_data_2": Node(
                name="fetch_data_2",
                type=NodeType.HTTP,
                depends_on=[],
                config=HTTPNodeConfig(url="https://api2.example.com"),
            ),
            "process_data": Node(
                name="process_data",
                type=NodeType.HTTP,
                depends_on=["fetch_data_1", "fetch_data_2"],
                config=HTTPNodeConfig(url="https://process.example.com"),
            ),
        },
        outputs={
            "result": "process_data",
        },
    )

    # Create engine with mock executor
    engine = WorkflowEngine()
    slow_executor = SlowHTTPNodeExecutor(delay=0.5)
    engine.executors[NodeType.HTTP] = slow_executor

    # Execute workflow
    start_time = time.time()
    context = await engine.execute(workflow, {})
    total_time = time.time() - start_time

    # Verify all nodes executed successfully
    assert context.errors == {}
    assert "fetch_data_1" in context.outputs
    assert "fetch_data_2" in context.outputs
    assert "process_data" in context.outputs

    # Verify parallel execution
    # If executed sequentially, it would take 1.5s (3 * 0.5s)
    # If executed in parallel, it should take ~1.0s (0.5s + 0.5s)
    assert (
        total_time < 1.2
    ), f"Execution took {total_time}s, expected < 1.2s for parallel execution"

    # Verify the two independent nodes started at approximately the same time
    time1 = slow_executor.call_times["fetch_data_1"]
    time2 = slow_executor.call_times["fetch_data_2"]
    start_diff = abs(time1["start"] - time2["start"])
    assert (
        start_diff < 0.1
    ), f"Independent nodes started {start_diff}s apart, should be < 0.1s"

    # Verify the dependent node started after both independent nodes finished
    time3 = slow_executor.call_times["process_data"]
    assert time3["start"] >= max(time1["end"], time2["end"])


@pytest.mark.asyncio
async def test_execution_groups_calculation():
    """Test that execution groups are calculated correctly"""
    workflow = Workflow(
        name="group-test",
        version="1.0.0",
        inputs={},
        nodes={
            # Level 0: No dependencies
            "a": Node(
                name="a",
                type=NodeType.HTTP,
                depends_on=[],
                config=HTTPNodeConfig(url="a"),
            ),
            "b": Node(
                name="b",
                type=NodeType.HTTP,
                depends_on=[],
                config=HTTPNodeConfig(url="b"),
            ),
            # Level 1: Depends on level 0
            "c": Node(
                name="c",
                type=NodeType.HTTP,
                depends_on=["a"],
                config=HTTPNodeConfig(url="c"),
            ),
            "d": Node(
                name="d",
                type=NodeType.HTTP,
                depends_on=["b"],
                config=HTTPNodeConfig(url="d"),
            ),
            # Level 2: Depends on level 1
            "e": Node(
                name="e",
                type=NodeType.HTTP,
                depends_on=["c", "d"],
                config=HTTPNodeConfig(url="e"),
            ),
        },
        outputs={},
    )

    engine = WorkflowEngine()
    groups = engine._get_execution_groups(workflow)

    # Should have 3 groups
    assert len(groups) == 3

    # Level 0: a and b
    assert set(groups[0]) == {"a", "b"}

    # Level 1: c and d
    assert set(groups[1]) == {"c", "d"}

    # Level 2: e
    assert set(groups[2]) == {"e"}


@pytest.mark.asyncio
async def test_parallel_execution_with_error():
    """Test that parallel execution handles errors correctly"""
    workflow = Workflow(
        name="error-test",
        version="1.0.0",
        inputs={},
        nodes={
            "node1": Node(
                name="node1",
                type=NodeType.HTTP,
                depends_on=[],
                config=HTTPNodeConfig(url="https://api1.example.com"),
            ),
            "node2": Node(
                name="node2",
                type=NodeType.HTTP,
                depends_on=[],
                config=HTTPNodeConfig(url="https://api2.example.com"),
            ),
            "node3": Node(
                name="node3",
                type=NodeType.HTTP,
                depends_on=["node1", "node2"],
                config=HTTPNodeConfig(url="https://api3.example.com"),
            ),
        },
        outputs={},
    )

    # Create engine with mock executor that fails for node2
    engine = WorkflowEngine()

    async def mock_execute(node: Node, context) -> NodeResult:  # noqa: ARG001
        if node.name == "node2":
            return NodeResult(
                output=None,
                success=False,
                error="Simulated failure",
            )
        return NodeResult(
            output={"data": f"Response from {node.name}"},
            success=True,
        )

    mock_executor = AsyncMock()
    mock_executor.execute.side_effect = mock_execute
    engine.executors[NodeType.HTTP] = mock_executor

    # Execute workflow
    context = await engine.execute(workflow, {})

    # Verify node1 succeeded, node2 failed, and node3 was not executed
    assert "node1" in context.outputs
    assert "node2" in context.errors
    assert context.errors["node2"] == "Simulated failure"
    assert "node3" not in context.outputs  # Should not execute due to failed dependency
