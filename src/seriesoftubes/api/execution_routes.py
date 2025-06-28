"""Execution management routes for the API"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from seriesoftubes.api.auth import get_current_active_user
from seriesoftubes.db import Execution, User, get_db
from seriesoftubes.db.database import async_session

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
    progress: dict[str, Any] | None
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
        ExecutionResponse(
            id=e.id,
            workflow_id=e.workflow_id,
            workflow_name=e.workflow.name,
            workflow_version=e.workflow.version,
            user_id=e.user_id,
            username=e.user.username,
            status=e.status if isinstance(e.status, str) else e.status.value,
            inputs=e.inputs or {},
            outputs=e.outputs,
            errors=e.errors,
            progress=e.progress or {},
            started_at=e.started_at.isoformat(),
            completed_at=e.completed_at.isoformat() if e.completed_at else None,
        )
        for e in executions
    ]


@router.get("/{execution_id}/stream")
async def stream_execution(
    execution_id: str,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Stream execution updates via Server-Sent Events"""
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"SSE stream request for execution {execution_id}")

    # Validate authentication token (SSE doesn't support headers)
    if not token:
        logger.error("No token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required in query parameter",
        )

    # Decode JWT token to get user
    try:
        from seriesoftubes.api.auth import ALGORITHM, SECRET_KEY

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            logger.error("Invalid token - no user ID")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )
        logger.info(f"Authenticated user: {user_id}")
    except JWTError as e:
        logger.error(f"JWT error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from e

    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id))
    current_user = result.scalar_one_or_none()

    if not current_user or not current_user.is_active:
        logger.error("User not found or inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Verify execution belongs to user
    result = await db.execute(
        select(Execution).where(
            Execution.id == execution_id,
            Execution.user_id == current_user.id,
        )
    )
    execution = result.scalar_one_or_none()

    if not execution:
        logger.error("Execution not found or not owned by user")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    logger.info(f"Starting SSE stream for execution {execution_id}, user {user_id}")

    async def event_generator():
        """Stream real-time execution updates"""
        import logging

        logger = logging.getLogger(__name__)

        logger.info(f"Starting SSE event generator for execution {execution_id}")

        try:
            # Send initial execution status
            async with async_session() as session:
                result = await session.execute(
                    select(Execution).where(Execution.id == execution_id)
                )
                current_execution = result.scalar_one_or_none()

                if current_execution:
                    yield f"data: {json.dumps({
                        'type': 'status',
                        'execution_id': execution_id,
                        'status': current_execution.status.value,
                        'started_at': current_execution.started_at.isoformat() if current_execution.started_at else None,
                        'completed_at': current_execution.completed_at.isoformat() if current_execution.completed_at else None,
                        'outputs': current_execution.outputs,
                        'errors': current_execution.errors,
                        'progress': current_execution.progress or {},
                    })}\n\n"

            # Poll for updates every 2 seconds
            last_status = None
            last_progress = {}
            poll_count = 0
            max_polls = 150  # 5 minutes maximum

            while poll_count < max_polls:
                async with async_session() as session:
                    result = await session.execute(
                        select(Execution).where(Execution.id == execution_id)
                    )
                    current_execution = result.scalar_one_or_none()

                    if current_execution:
                        current_status = current_execution.status.value
                        current_progress = current_execution.progress or {}

                        # Send update if status or progress changed
                        if (
                            current_status != last_status
                            or current_progress != last_progress
                        ):
                            yield f"data: {json.dumps({
                                'type': 'update',
                                'execution_id': execution_id,
                                'status': current_status,
                                'started_at': current_execution.started_at.isoformat() if current_execution.started_at else None,
                                'completed_at': current_execution.completed_at.isoformat() if current_execution.completed_at else None,
                                'outputs': current_execution.outputs,
                                'errors': current_execution.errors,
                                'progress': current_progress,
                            })}\n\n"
                            last_status = current_status
                            last_progress = current_progress

                        # Check if execution is complete
                        if current_status in ["COMPLETED", "FAILED", "CANCELLED"]:
                            yield f"data: {json.dumps({
                                'type': 'complete',
                                'execution_id': execution_id,
                                'status': current_status,
                                'started_at': current_execution.started_at.isoformat() if current_execution.started_at else None,
                                'completed_at': current_execution.completed_at.isoformat() if current_execution.completed_at else None,
                                'outputs': current_execution.outputs,
                                'errors': current_execution.errors,
                                'progress': current_progress,
                                'done': True
                            })}\n\n"
                            logger.info(
                                f"Execution {execution_id} completed with status {current_status}"
                            )
                            break

                await asyncio.sleep(2)
                poll_count += 1

            logger.info(f"SSE stream ended for execution {execution_id}")

        except Exception as e:
            logger.error(f"Error in SSE event generator: {e}")
            yield f"data: {json.dumps({
                'type': 'error',
                'error': str(e),
                'execution_id': execution_id
            })}\n\n"

    return EventSourceResponse(event_generator())


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
        status=execution.status if isinstance(execution.status, str) else execution.status.value,
        inputs=execution.inputs or {},
        outputs=execution.outputs,
        errors=execution.errors,
        progress=execution.progress or {},
        started_at=execution.started_at.isoformat(),
        completed_at=(
            execution.completed_at.isoformat() if execution.completed_at else None
        ),
    )
