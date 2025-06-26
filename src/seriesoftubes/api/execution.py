"""Execution management for API"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from seriesoftubes.engine import WorkflowEngine, run_workflow
from seriesoftubes.models import Workflow
from seriesoftubes.parser import parse_workflow_yaml


class ExecutionManager:
    """Manages workflow executions for the API"""

    def __init__(self) -> None:
        # In-memory storage for now
        # # TODO could be Redis in production
        self.executions: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, asyncio.Task[Any]] = {}

    async def run_workflow(
        self, workflow_path: Path, inputs: dict[str, Any] | None = None
    ) -> str:
        """Start a workflow execution asynchronously

        Returns:
            execution_id
        """
        execution_id = str(uuid4())

        # Parse workflow
        try:
            workflow = parse_workflow_yaml(workflow_path)
        except Exception as e:
            # Store error state
            self.executions[execution_id] = {
                "id": execution_id,
                "status": "failed",
                "workflow_path": str(workflow_path),
                "workflow_name": workflow_path.stem,
                "start_time": datetime.now(timezone.utc).isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }
            return execution_id

        # Initialize execution record
        self.executions[execution_id] = {
            "id": execution_id,
            "status": "running",
            "workflow_path": str(workflow_path),
            "workflow_name": workflow.name,
            "workflow_version": workflow.version,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": None,
            "outputs": None,
            "errors": None,
            "progress": {},
        }

        # Start execution task
        task = asyncio.create_task(
            self._execute_workflow(execution_id, workflow, inputs or {})
        )
        self.tasks[execution_id] = task

        return execution_id

    async def _execute_workflow(
        self, execution_id: str, workflow: Workflow, inputs: dict[str, Any]
    ) -> None:
        """Execute workflow and update status"""
        try:
            # Create custom engine that reports progress
            engine = ProgressTrackingEngine(execution_id, self.executions)
            context = await engine.execute(workflow, inputs)

            # Update final status
            self.executions[execution_id].update(
                {
                    "status": "completed" if not context.errors else "failed",
                    "end_time": datetime.now(timezone.utc).isoformat(),
                    "outputs": {
                        output_name: context.outputs.get(node_name)
                        for output_name, node_name in workflow.outputs.items()
                    },
                    "errors": context.errors if context.errors else None,
                }
            )

            # Save outputs to disk
            await run_workflow(workflow, inputs, output_dir=Path("outputs"))

        except Exception as e:
            self.executions[execution_id].update(
                {
                    "status": "failed",
                    "end_time": datetime.now(timezone.utc).isoformat(),
                    "error": str(e),
                }
            )

    def get_status(self, execution_id: str) -> dict[str, Any] | None:
        """Get execution status"""
        return self.executions.get(execution_id)

    def list_executions(self) -> list[dict[str, Any]]:
        """List all executions"""
        return list(self.executions.values())


class ProgressTrackingEngine(WorkflowEngine):
    """Workflow engine that tracks progress"""

    def __init__(self, execution_id: str, executions_store: dict[str, dict[str, Any]]):
        super().__init__()
        self.execution_id = execution_id
        self.executions_store = executions_store

    async def _execute_node(self, node: Any, context: Any) -> Any:
        """Override to track progress"""
        # Update progress before execution
        progress = self.executions_store[self.execution_id].get("progress", {})
        progress[node.name] = "running"
        self.executions_store[self.execution_id]["progress"] = progress

        # Execute node
        result = await super()._execute_node(node, context)

        # Update progress after execution
        progress[node.name] = "completed" if result.success else "failed"
        self.executions_store[self.execution_id]["progress"] = progress

        return result


# Global execution manager instance
execution_manager = ExecutionManager()
