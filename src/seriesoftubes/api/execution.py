"""Execution management for API"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from seriesoftubes.engine import (
    ExecutionContext,
    NodeResult,
    WorkflowEngine,
    run_workflow,
)
from seriesoftubes.models import Node, Workflow
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


class DatabaseProgressTrackingEngine(WorkflowEngine):
    """Workflow engine that tracks progress in database"""

    def __init__(self, execution_id: str, db_session: AsyncSession | None = None, user_id: str | None = None):
        super().__init__()
        self.execution_id = execution_id
        self.db_session = db_session  # For backward compatibility, but we'll create our own sessions
        self.user_id = user_id

    async def execute(
        self, workflow: Workflow, inputs: dict[str, Any]
    ) -> ExecutionContext:
        """Override execute to add cleanup logic and output storage"""
        try:
            # Execute the workflow normally
            context = await super().execute(workflow, inputs)

            # Save outputs to object storage
            if context.outputs:
                from seriesoftubes.engine import save_outputs_to_storage
                
                storage_keys = await save_outputs_to_storage(
                    execution_id=context.execution_id,
                    workflow_name=workflow.name,
                    outputs={
                        output_name: context.outputs.get(node_name)
                        for output_name, node_name in workflow.outputs.items()
                        if node_name in context.outputs
                    },
                    user_id=self.user_id,
                )
                
                # Store storage keys in context for later use
                context.storage_keys = storage_keys

            # Clean up any remaining "running" nodes after execution completes
            await self._cleanup_running_nodes()

            return context
        except Exception as e:
            # If execution fails, clean up any remaining "running" nodes
            await self._cleanup_running_nodes()
            raise e

    async def _cleanup_running_nodes(self):
        """Clean up any nodes still marked as 'running' when execution ends"""
        from sqlalchemy import select, update

        from seriesoftubes.db.models import Execution
        from seriesoftubes.db.database import async_session

        try:
            # Create a new session for cleanup to avoid greenlet issues
            async with async_session() as session:
                # Get current progress
                result_query = await session.execute(
                    select(Execution.progress).where(Execution.id == self.execution_id)
                )
                current_progress = result_query.scalar() or {}

                # Set any "running" nodes to "failed" since execution has ended
                cleanup_needed = False
                for node_name, status in current_progress.items():
                    if status == "running":
                        current_progress[node_name] = "failed"
                        cleanup_needed = True

                # Update database if cleanup was needed
                if cleanup_needed:
                    await session.execute(
                        update(Execution)
                        .where(Execution.id == self.execution_id)
                        .values(progress=current_progress)
                    )
                    await session.commit()

        except Exception as e:
            # Don't fail the execution just because cleanup failed
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to cleanup running nodes: {e}")

    async def _execute_node(self, node: Node, context: ExecutionContext) -> NodeResult:
        """Override to track progress in database"""
        from sqlalchemy import select, update

        from seriesoftubes.db.models import Execution
        from seriesoftubes.db.database import async_session

        try:
            # Create a new session for each database operation to avoid greenlet issues
            async with async_session() as session:
                # Get current progress
                result_query = await session.execute(
                    select(Execution.progress).where(Execution.id == self.execution_id)
                )
                current_progress = result_query.scalar() or {}

                # Update progress before execution - node is running
                current_progress[node.name] = "running"
                await session.execute(
                    update(Execution)
                    .where(Execution.id == self.execution_id)
                    .values(progress=current_progress)
                )
                await session.commit()

            # Execute node (outside of session context to avoid holding connection)
            result = await super()._execute_node(node, context)

            # Update progress after execution with detailed info
            async with async_session() as session:
                # Re-fetch current progress to avoid stale data
                result_query = await session.execute(
                    select(Execution.progress).where(Execution.id == self.execution_id)
                )
                current_progress = result_query.scalar() or {}

                if result.success:
                    current_progress[node.name] = {
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "output": result.output,
                    }
                else:
                    current_progress[node.name] = {
                        "status": "failed",
                        "error": result.error or "Node execution failed",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }

                await session.execute(
                    update(Execution)
                    .where(Execution.id == self.execution_id)
                    .values(progress=current_progress)
                )
                await session.commit()

            return result

        except Exception as e:
            # If we fail to update progress, still try to execute the node
            # but make sure to return an error result
            try:
                result = await super()._execute_node(node, context)
                return result
            except Exception:
                return NodeResult(
                    output=None, success=False, error=f"Node execution failed: {e}"
                )


# For backward compatibility
ProgressTrackingEngine = DatabaseProgressTrackingEngine


# Global execution manager instance
execution_manager = ExecutionManager()
