"""Execution management routes for the API"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from seriesoftubes.api.auth import get_current_active_user
from seriesoftubes.db import Execution, ExecutionStatus, User, get_db

router = APIRouter(prefix="/api/executions", tags=["executions"])


class ExecutionResponse(BaseModel):
    """Execution response"""

    model_config = {"from_attributes": True}

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

    model_config = {"from_attributes": True}

    execution_id: str
    status: str
    message: str


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
        ExecutionResponse.model_validate(e).model_copy(
            update={
                "workflow_name": e.workflow.name,
                "workflow_version": e.workflow.version,
                "username": e.user.username,
                "started_at": e.started_at.isoformat(),
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            }
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

    return ExecutionResponse.model_validate(execution).model_copy(
        update={
            "workflow_name": execution.workflow.name,
            "workflow_version": execution.workflow.version,
            "username": execution.user.username,
            "started_at": execution.started_at.isoformat(),
            "completed_at": (
                execution.completed_at.isoformat() if execution.completed_at else None
            ),
        }
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
            if current_status in [
                ExecutionStatus.COMPLETED.value,
                ExecutionStatus.FAILED.value,
            ]:
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
