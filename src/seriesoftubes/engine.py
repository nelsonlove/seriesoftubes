"""DAG execution engine for seriesoftubes workflows"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from seriesoftubes.models import Node, NodeType, Workflow
from seriesoftubes.nodes import (
    FileNodeExecutor,
    HTTPNodeExecutor,
    LLMNodeExecutor,
    NodeExecutor,
    NodeResult,
    RouteNodeExecutor,
)


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
            NodeType.FILE: FileNodeExecutor(),
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

        # Get execution order and groups for parallel execution
        execution_groups = self._get_execution_groups(workflow)

        # Execute nodes in parallel groups
        for group in execution_groups:
            # Skip if we've encountered errors (fail fast)
            if context.errors:
                break

            # Execute all nodes in this group in parallel
            tasks = []
            for node_name in group:
                node = workflow.nodes[node_name]

                # Check if we should skip this node (for routing)
                if self._should_skip_node(node, context):
                    continue

                # Create task for this node
                tasks.append(self._execute_node_async(node_name, node, context))

            # Wait for all tasks in this group to complete
            if tasks:
                await asyncio.gather(*tasks)

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

    async def _execute_node_async(
        self, node_name: str, node: Node, context: ExecutionContext
    ) -> None:
        """Execute a node and update context (for parallel execution)"""
        try:
            result = await self._execute_node(node, context)
            if result.success:
                context.set_output(node_name, result.output)
            else:
                context.set_error(node_name, result.error or "Unknown error")
        except Exception as e:
            context.set_error(node_name, str(e))

    def _get_execution_groups(self, workflow: Workflow) -> list[list[str]]:
        """Group nodes by execution level for parallel processing

        Returns list of groups where each group contains nodes that can run in parallel
        """
        nodes = workflow.nodes
        levels: dict[str, int] = {}  # Node name -> execution level

        # Calculate execution level for each node
        def get_level(node_name: str) -> int:
            if node_name in levels:
                return levels[node_name]

            node = nodes[node_name]
            if not node.depends_on:
                levels[node_name] = 0
            else:
                # Level is max of dependencies + 1
                dep_levels = [get_level(dep) for dep in node.depends_on]
                levels[node_name] = max(dep_levels) + 1

            return levels[node_name]

        # Calculate levels for all nodes
        for node_name in nodes:
            get_level(node_name)

        # Group nodes by level
        max_level = max(levels.values()) if levels else -1
        groups = []
        for level in range(max_level + 1):
            group = [name for name, node_level in levels.items() if node_level == level]
            if group:
                groups.append(group)

        return groups


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
