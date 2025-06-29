"""Celery tasks for workflow execution"""

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from celery import Celery, Task
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from seriesoftubes.api.execution import DatabaseProgressTrackingEngine
from seriesoftubes.db import ExecutionStatus as DBExecutionStatus
from seriesoftubes.db.database import async_session, engine
from seriesoftubes.db.models import Execution
from seriesoftubes.parser import parse_workflow_yaml

logger = logging.getLogger(__name__)

# Create Celery app
app = Celery('seriesoftubes')
app.config_from_object('seriesoftubes.celery_config')


@app.task(bind=True, name='seriesoftubes.execute_workflow')
def execute_workflow(
    self,
    execution_id: str,
    workflow_yaml: str,
    inputs: dict,
    user_id: str,
):
    """Execute a workflow in a Celery worker
    
    Args:
        execution_id: UUID of the execution record
        workflow_yaml: YAML content of the workflow
        inputs: Input values for the workflow
        user_id: ID of the user running the workflow
    """
    import asyncio
    
    logger.info(f"Worker starting execution {execution_id}")
    
    # Run the async function in a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            _execute_workflow_async(execution_id, workflow_yaml, inputs, user_id)
        )
    finally:
        loop.close()


async def _execute_workflow_async(
    execution_id: str,
    workflow_yaml: str,
    inputs: dict,
    user_id: str,
):
    """Async implementation of workflow execution"""
    async with async_session() as session:
        try:
            # Update status to running
            await session.execute(
                update(Execution)
                .where(Execution.id == execution_id)
                .values(status=DBExecutionStatus.RUNNING.value)
            )
            await session.commit()

            # Parse workflow from YAML
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
                tmp.write(workflow_yaml)
                tmp_path = Path(tmp.name)

            try:
                parsed = parse_workflow_yaml(tmp_path)

                # Create engine without passing session (it will create its own)
                engine = DatabaseProgressTrackingEngine(execution_id, None, user_id)
                
                # Execute workflow
                context = await engine.execute(parsed, inputs)
                
                logger.info(
                    f"Completed execution {execution_id} with status: "
                    f"{'success' if not context.errors else 'failed'}"
                )

                # Prepare outputs
                outputs = {}
                for output_name, node_name in parsed.outputs.items():
                    if node_name in context.outputs:
                        outputs[output_name] = context.outputs[node_name]

                # Determine final status
                final_status = (
                    DBExecutionStatus.COMPLETED.value
                    if not context.errors
                    else DBExecutionStatus.FAILED.value
                )

                # Update execution record
                execution_update = {
                    "status": final_status,
                    "outputs": outputs,
                    "errors": context.errors if context.errors else None,
                    "completed_at": datetime.now(timezone.utc),
                }
                
                if hasattr(context, 'error_details') and context.error_details:
                    execution_update["error_details"] = context.error_details
                
                if hasattr(context, 'storage_keys') and context.storage_keys:
                    execution_update["storage_keys"] = context.storage_keys
                
                await session.execute(
                    update(Execution)
                    .where(Execution.id == execution_id)
                    .values(**execution_update)
                )
                await session.commit()

            finally:
                tmp_path.unlink()

        except Exception as e:
            logger.error(f"Execution {execution_id} failed: {e}", exc_info=True)
            
            # Update execution as failed
            await session.execute(
                update(Execution)
                .where(Execution.id == execution_id)
                .values(
                    status=DBExecutionStatus.FAILED.value,
                    errors={"error": str(e)},
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
            
            # Re-raise for Celery to handle retries if configured
            raise


@app.task(bind=True, name='seriesoftubes.execute_node')
def execute_node(self, node_data: dict, context_data: dict):
    """Execute a single node - for distributed node execution
    
    This would allow distributing individual nodes across workers
    for better parallelization of large workflows.
    """
    # TODO: Implement distributed node execution
    pass