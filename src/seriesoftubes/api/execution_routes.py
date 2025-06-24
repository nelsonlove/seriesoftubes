"""Execution management routes for the API"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from seriesoftubes.api.auth import get_current_active_user
from seriesoftubes.api.execution import execution_manager
from seriesoftubes.api.models import WorkflowRunRequest
from seriesoftubes.db import Execution, ExecutionStatus, User, Workflow, get_db
from seriesoftubes.parser import parse_workflow_yaml

router = APIRouter(prefix="/api/executions", tags=["executions"])


class ExecutionResponse(BaseModel):
    """Execution response"""

    id: str
    workflow_id: str
    workflow_name: str
    workflow_version: str
    user_id: str
    username: str
    status: str
    inputs: dict[str, Any]
    outputs: dict[str, Any] | None
    errors: dict[str, str] | None
    started_at: str
    completed_at: str | None


class ExecutionCreateResponse(BaseModel):
    """Response when creating an execution"""

    execution_id: str
    status: str
    message: str


@router.post("/workflows/{workflow_id}/run", response_model=ExecutionCreateResponse)
async def run_workflow(
    workflow_id: str,
    request: WorkflowRunRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionCreateResponse:
    """Run a workflow from the database"""
    # Get workflow
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            (Workflow.user_id == current_user.id) | (Workflow.is_public == True),
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Create execution record
    execution = Execution(
        workflow_id=workflow.id,
        user_id=current_user.id,
        status=ExecutionStatus.PENDING.value,
        inputs=request.inputs,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Start execution asynchronously
    workflow_path = Path(workflow.package_path) / "workflow.yaml"
    
    async def run_and_update():
        """Run workflow and update database"""
        async with AsyncSession(db.bind) as session:
            try:
                # Get execution from new session
                result = await session.execute(
                    select(Execution).where(Execution.id == execution.id)
                )
                exec_record = result.scalar_one()
                
                # Update status to running
                exec_record.status = ExecutionStatus.RUNNING.value
                await session.commit()

                # Run workflow
                exec_id = await execution_manager.run_workflow(workflow_path, request.inputs)
                
                # Wait for completion and get results
                while True:
                    status_data = execution_manager.get_status(exec_id)
                    if status_data["status"] in ["completed", "failed"]:
                        break
                    await asyncio.sleep(0.5)

                # Update execution record
                exec_record.status = (
                    ExecutionStatus.COMPLETED.value
                    if status_data["status"] == "completed"
                    else ExecutionStatus.FAILED.value
                )
                exec_record.outputs = status_data.get("outputs")
                exec_record.errors = status_data.get("errors")
                exec_record.completed_at = datetime.now(timezone.utc)
                await session.commit()

            except Exception as e:
                # Update execution as failed
                exec_record.status = ExecutionStatus.FAILED.value
                exec_record.errors = {"error": str(e)}
                exec_record.completed_at = datetime.now(timezone.utc)
                await session.commit()

    # Start execution in background
    asyncio.create_task(run_and_update())

    return ExecutionCreateResponse(
        execution_id=execution.id,
        status="started",
        message=f"Workflow execution started with ID: {execution.id}",
    )


@router.get("", response_model=list[ExecutionResponse])
async def list_executions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
) -> list[ExecutionResponse]:
    """List user's executions"""
    result = await db.execute(
        select(Execution)
        .options(selectinload(Execution.workflow), selectinload(Execution.user))
        .where(Execution.user_id == current_user.id)
        .order_by(Execution.started_at.desc())
        .limit(limit)
    )
    executions = result.scalars().all()

    return [
        ExecutionResponse(
            id=e.id,
            workflow_id=e.workflow_id,
            workflow_name=e.workflow.name,
            workflow_version=e.workflow.version,
            user_id=e.user_id,
            username=e.user.username,
            status=e.status,
            inputs=e.inputs,
            outputs=e.outputs,
            errors=e.errors,
            started_at=e.started_at.isoformat(),
            completed_at=e.completed_at.isoformat() if e.completed_at else None,
        )
        for e in executions
    ]


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutionResponse:
    """Get a specific execution"""
    result = await db.execute(
        select(Execution)
        .options(selectinload(Execution.workflow), selectinload(Execution.user))
        .where(
            Execution.id == execution_id,
            Execution.user_id == current_user.id,
        )
    )
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    return ExecutionResponse(
        id=execution.id,
        workflow_id=execution.workflow_id,
        workflow_name=execution.workflow.name,
        workflow_version=execution.workflow.version,
        user_id=execution.user_id,
        username=execution.user.username,
        status=execution.status,
        inputs=execution.inputs,
        outputs=execution.outputs,
        errors=execution.errors,
        started_at=execution.started_at.isoformat(),
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
    )


@router.get("/{execution_id}/stream")
async def stream_execution(
    execution_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Stream execution updates via Server-Sent Events"""
    # Verify execution belongs to user
    result = await db.execute(
        select(Execution).where(
            Execution.id == execution_id,
            Execution.user_id == current_user.id,
        )
    )
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    async def event_generator() -> Any:
        """Generate SSE events for execution updates"""
        last_status = None

        while True:
            # Refresh execution from database
            await db.refresh(execution)

            # Check for status changes
            current_status = execution.status

            if current_status != last_status:
                yield {
                    "event": "update",
                    "data": json.dumps(
                        {
                            "execution_id": execution_id,
                            "status": current_status,
                            "outputs": execution.outputs,
                            "errors": execution.errors,
                        }
                    ),
                }
                last_status = current_status

            # If execution is complete, send final event and close
            if current_status in [ExecutionStatus.COMPLETED.value, ExecutionStatus.FAILED.value]:
                yield {
                    "event": "complete",
                    "data": json.dumps(
                        {
                            "execution_id": execution_id,
                            "status": current_status,
                            "outputs": execution.outputs,
                            "errors": execution.errors,
                        }
                    ),
                }
                break

            # Wait before checking again
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())