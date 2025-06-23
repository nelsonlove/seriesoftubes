"""Tests for the workflow execution engine"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from seriesoftubes.engine import ExecutionContext, WorkflowEngine, run_workflow
from seriesoftubes.models import (
    Node,
    NodeType,
    RouteCondition,
    RouteNodeConfig,
    Workflow,
    WorkflowInput,
)
from seriesoftubes.nodes import NodeResult


@pytest.fixture
def simple_workflow():
    """Create a simple test workflow"""
    return Workflow(
        name="test_workflow",
        inputs={
            "text": WorkflowInput(required=True),
            "optional": WorkflowInput(required=False, default="default_value"),
        },
        nodes={
            "route_node": Node(
                name="route_node",
                type=NodeType.ROUTE,
                depends_on=[],
                config=RouteNodeConfig(
                    routes=[
                        RouteCondition(when="inputs.text == 'hello'", to="hello_path"),
                        RouteCondition(default=True, to="default_path"),
                    ]
                ),
            )
        },
        outputs={"result": "route_node"},
    )


class TestExecutionContext:
    """Test ExecutionContext class"""

    def test_context_creation(self, simple_workflow):
        """Test creating execution context"""
        inputs = {"text": "hello"}
        context = ExecutionContext(simple_workflow, inputs)

        assert context.workflow == simple_workflow
        assert context.inputs == inputs
        assert context.outputs == {}
        assert context.errors == {}
        assert context.execution_id is not None
        assert context.start_time is not None

    def test_context_methods(self, simple_workflow):
        """Test context methods"""
        context = ExecutionContext(simple_workflow, {"text": "hello"})

        # Test setting and getting output
        context.set_output("node1", {"data": "value"})
        assert context.get_output("node1") == {"data": "value"}
        assert context.get_output("nonexistent") is None

        # Test getting input
        assert context.get_input("text") == "hello"
        assert context.get_input("nonexistent") is None

        # Test setting error
        context.set_error("node1", "Something went wrong")
        assert context.errors["node1"] == "Something went wrong"


class TestWorkflowEngine:
    """Test WorkflowEngine class"""

    def test_engine_initialization(self):
        """Test engine initialization"""
        engine = WorkflowEngine()
        assert NodeType.LLM in engine.executors
        assert NodeType.HTTP in engine.executors
        assert NodeType.ROUTE in engine.executors

    def test_validate_inputs(self, simple_workflow):
        """Test input validation"""
        engine = WorkflowEngine()

        # Valid inputs
        validated = engine._validate_inputs(
            simple_workflow, {"text": "hello", "extra": "ignored"}
        )
        assert validated == {"text": "hello", "optional": "default_value"}

        # Missing required input
        with pytest.raises(ValueError, match="Required input 'text' not provided"):
            engine._validate_inputs(simple_workflow, {})

        # With default value
        validated = engine._validate_inputs(simple_workflow, {"text": "hello"})
        assert validated["optional"] == "default_value"

    @pytest.mark.asyncio
    async def test_execute_workflow(self, simple_workflow):
        """Test executing a workflow"""
        engine = WorkflowEngine()

        # Mock the route executor
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = NodeResult(
            output="hello_path", success=True
        )
        engine.executors[NodeType.ROUTE] = mock_executor

        # Execute workflow
        context = await engine.execute(simple_workflow, {"text": "hello"})

        # Check results
        assert context.outputs["route_node"] == "hello_path"
        assert len(context.errors) == 0
        mock_executor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_error(self, simple_workflow):
        """Test executing a workflow with an error"""
        engine = WorkflowEngine()

        # Mock executor to return an error
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = NodeResult(
            output=None, success=False, error="Test error"
        )
        engine.executors[NodeType.ROUTE] = mock_executor

        # Execute workflow
        context = await engine.execute(simple_workflow, {"text": "hello"})

        # Check error was recorded
        assert "route_node" in context.errors
        assert context.errors["route_node"] == "Test error"
        assert "route_node" not in context.outputs


@pytest.mark.asyncio
async def test_run_workflow(simple_workflow, tmp_path):
    """Test the high-level run_workflow function"""
    # Mock the engine execution
    mock_context = MagicMock()
    mock_context.execution_id = "test-id"
    mock_context.start_time = MagicMock(isoformat=lambda: "2023-01-01T00:00:00")
    mock_context.errors = {}
    mock_context.outputs = {"route_node": "hello_path"}

    with patch(
        "seriesoftubes.engine.WorkflowEngine.execute", return_value=mock_context
    ):
        # Run workflow with custom output directory
        results = await run_workflow(
            simple_workflow, {"text": "hello"}, output_dir=tmp_path / "outputs"
        )

        # Check results
        assert results["success"] is True
        assert results["outputs"]["result"] == "hello_path"
        assert results["execution_id"] == "test-id"

        # Check files were saved
        output_dir = tmp_path / "outputs" / "test-id"
        assert output_dir.exists()
        assert (output_dir / "execution.json").exists()
        assert (output_dir / "route_node.json").exists()

        # Verify execution.json content
        with open(output_dir / "execution.json") as f:
            saved_results = json.load(f)
            assert saved_results["success"] is True
            assert saved_results["outputs"]["result"] == "hello_path"


@pytest.mark.asyncio
async def test_run_workflow_no_save(simple_workflow, tmp_path):
    """Test running workflow without saving outputs"""
    mock_context = MagicMock()
    mock_context.execution_id = "test-id"
    mock_context.start_time = MagicMock(isoformat=lambda: "2023-01-01T00:00:00")
    mock_context.errors = {}
    mock_context.outputs = {"route_node": "hello_path"}

    with patch(
        "seriesoftubes.engine.WorkflowEngine.execute", return_value=mock_context
    ):
        # Run without saving
        results = await run_workflow(
            simple_workflow,
            {"text": "hello"},
            save_outputs=False,
            output_dir=tmp_path / "outputs",
        )

        # Check results
        assert results["success"] is True
        assert results["outputs"]["result"] == "hello_path"

        # Ensure no files were created for this execution
        assert not (tmp_path / "outputs" / "test-id").exists()
