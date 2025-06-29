"""Synchronous execution tracking for use in Celery workers"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from seriesoftubes.engine import ExecutionContext, NodeResult, WorkflowEngine
from seriesoftubes.models import Node, Workflow

logger = logging.getLogger(__name__)


class SyncDatabaseProgressTrackingEngine(WorkflowEngine):
    """Workflow engine that tracks progress using synchronous database operations
    
    This is designed to work within Celery's synchronous context without
    event loop conflicts.
    """

    def __init__(self, execution_id: str, db_url: str, user_id: str | None = None):
        super().__init__()
        self.execution_id = execution_id
        self.user_id = user_id
        
        # Create synchronous engine
        sync_db_url = db_url.replace("+asyncpg", "")
        self.engine = create_engine(sync_db_url)

    async def execute(self, workflow: Workflow, inputs: dict[str, Any]) -> ExecutionContext:
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
            self._cleanup_running_nodes_sync()

            return context
        except Exception as e:
            # If execution fails, clean up any remaining "running" nodes
            self._cleanup_running_nodes_sync()
            raise e

    def _cleanup_running_nodes_sync(self):
        """Clean up any nodes still marked as 'running' when execution ends (sync version)"""
        from seriesoftubes.db.models import Execution

        try:
            with Session(self.engine) as session:
                # Get current progress
                result = session.execute(
                    select(Execution.progress).where(Execution.id == self.execution_id)
                )
                current_progress = result.scalar() or {}

                # Set any "running" nodes to "failed" since execution has ended
                cleanup_needed = False
                for node_name, status in current_progress.items():
                    if status == "running":
                        current_progress[node_name] = "failed"
                        cleanup_needed = True

                # Update database if cleanup was needed
                if cleanup_needed:
                    session.execute(
                        update(Execution)
                        .where(Execution.id == self.execution_id)
                        .values(progress=current_progress)
                    )
                    session.commit()

        except Exception as e:
            # Don't fail the execution just because cleanup failed
            logger.warning(f"Failed to cleanup running nodes: {e}")

    async def _execute_node(self, node: Node, context: ExecutionContext) -> NodeResult:
        """Override to track progress in database using sync operations"""
        logger.info(f"SyncDatabaseProgressTrackingEngine._execute_node called for node: {node.name}")
        
        from seriesoftubes.db.models import Execution

        # Update progress before execution - node is running
        try:
            with Session(self.engine) as session:
                # Get current progress
                result = session.execute(
                    select(Execution.progress).where(Execution.id == self.execution_id)
                )
                current_progress = result.scalar() or {}

                # Update progress before execution - node is running
                current_progress[node.name] = "running"
                session.execute(
                    update(Execution)
                    .where(Execution.id == self.execution_id)
                    .values(progress=current_progress)
                )
                session.commit()
                
                logger.info(f"Updated progress for execution {self.execution_id}: {current_progress}")

        except Exception as e:
            logger.error(f"Failed to update progress before node execution: {e}")

        # Execute the node
        try:
            # Execute node normally (async operation is fine here)
            result = await super()._execute_node(node, context)
        except Exception as e:
            # Node execution failed - create error result
            logger.error(f"Node {node.name} execution failed: {e}")
            result = NodeResult(
                output=None,
                success=False,
                error=f"Node execution error: {str(e)}"
            )

        # Update progress after execution with detailed info
        try:
            with Session(self.engine) as session:
                # Re-fetch current progress to avoid stale data
                result_query = session.execute(
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

                session.execute(
                    update(Execution)
                    .where(Execution.id == self.execution_id)
                    .values(progress=current_progress)
                )
                session.commit()
                
                logger.info(f"Updated progress after node execution: {node.name} -> {current_progress[node.name]['status']}")

        except Exception as e:
            logger.error(f"Failed to update progress after node execution: {e}")

        return result