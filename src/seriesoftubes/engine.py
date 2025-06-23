"""DAG execution engine for seriesoftubes workflows"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from seriesoftubes.models import Node, NodeType, Workflow
from seriesoftubes.nodes import (
    HTTPNodeExecutor,
    LLMNodeExecutor,
    NodeExecutor,
    NodeResult,
    RouteNodeExecutor,
)
from seriesoftubes.parser import topological_sort


class ExecutionContext:
    """Context for workflow execution"""

    def __init__(self, workflow: Workflow, inputs: dict[str, Any]):
        self.workflow = workflow
        self.inputs = inputs
        self.outputs: dict[str, Any] = {}
        self.errors: dict[str, str] = {}
        self.execution_id = str(uuid4())
        self.start_time = datetime.now(timezone.utc)

    def get_output(self, node_name: str) -> Any:
        """Get output from a previous node"""
        return self.outputs.get(node_name)

    def get_input(self, input_name: str) -> Any:
        """Get workflow input value"""
        return self.inputs.get(input_name)

    def set_output(self, node_name: str, output: Any) -> None:
        """Store output from a node"""
        self.outputs[node_name] = output

    def set_error(self, node_name: str, error: str) -> None:
        """Store error from a node"""
        self.errors[node_name] = error


class WorkflowEngine:
    """Engine for executing workflows"""

    def __init__(self) -> None:
        # Map node types to their executors
        self.executors: dict[NodeType, NodeExecutor] = {
            NodeType.LLM: LLMNodeExecutor(),
            NodeType.HTTP: HTTPNodeExecutor(),
            NodeType.ROUTE: RouteNodeExecutor(),
        }

    async def execute(
        self, workflow: Workflow, inputs: dict[str, Any] | None = None
    ) -> ExecutionContext:
        """Execute a workflow

        Args:
            workflow: The workflow to execute
            inputs: Input values for the workflow

        Returns:
            ExecutionContext with results
        """
        # Validate and prepare inputs
        validated_inputs = self._validate_inputs(workflow, inputs or {})

        # Create execution context
        context = ExecutionContext(workflow, validated_inputs)

        # Get execution order
        execution_order = topological_sort(workflow)

        # Execute nodes in order
        for node_name in execution_order:
            node = workflow.nodes[node_name]

            # Check if we should skip this node (for routing)
            if self._should_skip_node(node, context):
                continue

            # Execute the node
            try:
                result = await self._execute_node(node, context)
                if result.success:
                    context.set_output(node_name, result.output)
                else:
                    context.set_error(node_name, result.error or "Unknown error")
                    # For now, fail fast on errors
                    break
            except Exception as e:
                context.set_error(node_name, str(e))
                break

        return context

    def _validate_inputs(
        self, workflow: Workflow, provided_inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate and prepare workflow inputs"""
        validated = {}

        for input_name, input_def in workflow.inputs.items():
            if input_name in provided_inputs:
                # TODO: Add type validation based on input_def.input_type
                validated[input_name] = provided_inputs[input_name]
            elif input_def.required:
                msg = f"Required input '{input_name}' not provided"
                raise ValueError(msg)
            elif input_def.default is not None:
                validated[input_name] = input_def.default

        # Warn about extra inputs
        extra_inputs = set(provided_inputs.keys()) - set(workflow.inputs.keys())
        if extra_inputs:
            # For now, just ignore extra inputs
            pass

        return validated

    def _should_skip_node(self, node: Node, context: ExecutionContext) -> bool:
        """Check if a node should be skipped

        This is used for routing - if a route node has already selected
        a path, we should skip nodes that aren't on that path.
        """
        # For MVP, we execute all nodes
        # In the future, we'll implement proper path pruning based on route decisions
        _ = node, context  # Will be used in future implementation
        return False

    async def _execute_node(self, node: Node, context: ExecutionContext) -> NodeResult:
        """Execute a single node"""
        # Get the appropriate executor
        executor = self.executors.get(node.node_type)
        if not executor:
            return NodeResult(
                output=None,
                success=False,
                error=f"No executor for node type: {node.node_type}",
            )

        # Execute the node
        return await executor.execute(node, context)


async def run_workflow(
    workflow: Workflow,
    inputs: dict[str, Any] | None = None,
    *,
    save_outputs: bool = True,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """High-level function to run a workflow

    Args:
        workflow: The workflow to execute
        inputs: Input values
        save_outputs: Whether to save outputs to disk
        output_dir: Base directory for outputs (defaults to ./outputs)

    Returns:
        Dictionary with execution results
    """
    engine = WorkflowEngine()
    context = await engine.execute(workflow, inputs)

    # Prepare results
    results: dict[str, Any] = {
        "execution_id": context.execution_id,
        "start_time": context.start_time.isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "success": len(context.errors) == 0,
        "outputs": {},
        "errors": context.errors,
    }

    # Map final outputs
    for output_name, node_name in workflow.outputs.items():
        if node_name in context.outputs:
            results["outputs"][output_name] = context.outputs[node_name]

    # Save outputs if requested
    if save_outputs:
        base_dir = output_dir or Path("outputs")
        exec_output_dir = base_dir / context.execution_id
        exec_output_dir.mkdir(parents=True, exist_ok=True)

        # Save execution summary
        import json

        with open(exec_output_dir / "execution.json", "w") as f:
            json.dump(results, f, indent=2)

        # Save individual node outputs
        for node_name, output in context.outputs.items():
            with open(exec_output_dir / f"{node_name}.json", "w") as f:
                json.dump(output, f, indent=2)

    return results
