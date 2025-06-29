"""Synchronous Celery tasks for workflow execution

This module uses synchronous database operations to avoid greenlet issues
in Celery worker context.
"""

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from celery import Celery
from sqlalchemy import create_engine, update, select
from sqlalchemy.orm import Session

from seriesoftubes.db import ExecutionStatus as DBExecutionStatus
from seriesoftubes.db.models import Execution
from seriesoftubes.parser import parse_workflow_yaml
import os

logger = logging.getLogger(__name__)

# Create Celery app
app = Celery('seriesoftubes')
app.config_from_object('seriesoftubes.celery_config')

# Create synchronous engine for Celery tasks
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://seriesoftubes:development-password@localhost:5432/seriesoftubes")
# Convert async URL to sync URL
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")
sync_engine = create_engine(SYNC_DATABASE_URL)


def get_sync_db():
    """Get a synchronous database session"""
    with Session(sync_engine) as session:
        yield session


@app.task(bind=True, name='seriesoftubes.execute_workflow')
def execute_workflow(
    self,
    execution_id: str,
    workflow_yaml: str,
    inputs: dict,
    user_id: str,
):
    """Execute a workflow in a Celery worker using synchronous operations
    
    Args:
        execution_id: UUID of the execution record
        workflow_yaml: YAML content of the workflow
        inputs: Input values for the workflow
        user_id: ID of the user running the workflow
    """
    logger.info(f"Worker starting execution {execution_id}")
    
    with Session(sync_engine) as session:
        try:
            # Update status to running
            session.execute(
                update(Execution)
                .where(Execution.id == execution_id)
                .values(status=DBExecutionStatus.RUNNING.value)
            )
            session.commit()

            # Parse workflow from YAML
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
                tmp.write(workflow_yaml)
                tmp_path = Path(tmp.name)

            try:
                parsed = parse_workflow_yaml(tmp_path)

                # We need to run the async engine in a separate event loop
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Import sync engine here to avoid circular imports
                    from seriesoftubes.api.execution_sync import SyncDatabaseProgressTrackingEngine
                    
                    # Create sync engine with database URL
                    engine = SyncDatabaseProgressTrackingEngine(execution_id, SYNC_DATABASE_URL, user_id)
                    
                    # Execute workflow in async context
                    context = loop.run_until_complete(
                        engine.execute(parsed, inputs)
                    )
                    
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

                    # Update execution record using sync session
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
                    
                    session.execute(
                        update(Execution)
                        .where(Execution.id == execution_id)
                        .values(**execution_update)
                    )
                    session.commit()
                    
                finally:
                    loop.close()

            finally:
                tmp_path.unlink()

        except Exception as e:
            logger.error(f"Execution {execution_id} failed: {e}", exc_info=True)
            
            # Update execution as failed
            session.execute(
                update(Execution)
                .where(Execution.id == execution_id)
                .values(
                    status=DBExecutionStatus.FAILED.value,
                    errors={"error": str(e)},
                    completed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
            
            # Re-raise for Celery to handle retries if configured
            raise


@app.task(bind=True, name='seriesoftubes.cleanup_stale_executions')
def cleanup_stale_executions(self):
    """Clean up executions that are stuck in running state
    
    This task should be run periodically to clean up executions
    that failed to update their status properly.
    """
    from datetime import timedelta
    
    logger.info("Cleaning up stale executions")
    
    with Session(sync_engine) as session:
        # Find executions that have been running for more than 1 hour
        stale_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        result = session.execute(
            select(Execution)
            .where(Execution.status == DBExecutionStatus.RUNNING.value)
            .where(Execution.started_at < stale_time)
        )
        
        stale_executions = result.scalars().all()
        
        for execution in stale_executions:
            logger.warning(f"Marking stale execution {execution.id} as failed")
            
            session.execute(
                update(Execution)
                .where(Execution.id == execution.id)
                .values(
                    status=DBExecutionStatus.FAILED.value,
                    errors={"error": "Execution timed out or worker died"},
                    completed_at=datetime.now(timezone.utc),
                )
            )
        
        session.commit()
        
        logger.info(f"Cleaned up {len(stale_executions)} stale executions")


# Set up periodic task for cleanup
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-stale-executions': {
        'task': 'seriesoftubes.cleanup_stale_executions',
        'schedule': crontab(minute='*/15'),  # Run every 15 minutes
    },
}