"""Execution management routes for the API"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from seriesoftubes.api.auth import get_current_active_user, get_current_user_sse
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
    error_details: dict[str, dict[str, Any]] | None
    progress: dict[str, Any] | None
    storage_keys: dict[str, str] | None
    started_at: str
    completed_at: str | None


class ExecutionListResponse(BaseModel):
    """Lighter execution response for list views"""

    model_config = {"from_attributes": True}

    id: str
    workflow_id: str
    workflow_name: str
    workflow_version: str
    user_id: str
    username: str
    status: str
    started_at: str
    completed_at: str | None
    # Exclude large fields: inputs, outputs, errors, error_details, progress


class ExecutionCreateResponse(BaseModel):
    """Response when creating an execution"""

    model_config = {"from_attributes": True}

    execution_id: str
    status: str
    message: str


@router.get("", response_model=list[ExecutionListResponse])
async def list_executions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,  # Reduced default limit
    offset: int = 0,
) -> list[ExecutionListResponse]:
    """List user's executions"""
    result = await db.execute(
        select(Execution)
        .options(selectinload(Execution.workflow), selectinload(Execution.user))
        .where(Execution.user_id == current_user.id)
        .order_by(Execution.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    executions = result.scalars().all()

    return [
        ExecutionListResponse(
            id=e.id,
            workflow_id=e.workflow_id,
            workflow_name=e.workflow.name,
            workflow_version=e.workflow.version,
            user_id=e.user_id,
            username=e.user.username,
            status=e.status if isinstance(e.status, str) else e.status.value,
            started_at=e.started_at.isoformat(),
            completed_at=e.completed_at.isoformat() if e.completed_at else None,
        )
        for e in executions
    ]


@router.get("/{execution_id}/stream")
async def stream_execution(
    execution_id: str,
    token: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Stream execution updates via Server-Sent Events"""
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"SSE stream request for execution {execution_id}, token present: {bool(token)}")

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
                    select(
                        Execution.id,
                        Execution.status,
                        Execution.started_at,
                        Execution.completed_at,
                        Execution.outputs,
                        Execution.errors,
                        Execution.error_details,
                        Execution.progress
                    ).where(Execution.id == execution_id)
                )
                row = result.one_or_none()

                if row:
                    (
                        exec_id, status, started_at, completed_at,
                        outputs, errors, error_details, progress
                    ) = row
                    
                    yield f"data: {json.dumps({
                        'type': 'status',
                        'execution_id': execution_id,
                        'status': status if isinstance(status, str) else status.value,
                        'started_at': started_at.isoformat() if started_at else None,
                        'completed_at': completed_at.isoformat() if completed_at else None,
                        'outputs': outputs,
                        'errors': errors,
                        'error_details': error_details,
                        'progress': progress or {},
                    })}\n\n"

            # Poll for updates every 2 seconds
            last_status = None
            last_progress = {}
            poll_count = 0
            max_polls = 150  # 5 minutes maximum

            while poll_count < max_polls:
                row = None
                try:
                    async with async_session() as session:
                        # Only select the fields we need to reduce memory usage
                        result = await session.execute(
                            select(
                                Execution.id,
                                Execution.status,
                                Execution.started_at,
                                Execution.completed_at,
                                Execution.outputs,
                                Execution.errors,
                                Execution.error_details,
                                Execution.progress
                            ).where(Execution.id == execution_id)
                        )
                        row = result.one_or_none()
                        
                        # Explicitly close the session to free resources
                        await session.close()
                except Exception as e:
                    logger.error(f"Error polling execution {execution_id}: {e}")
                    # Continue polling on error
                    await asyncio.sleep(2)
                    poll_count += 1
                    continue

                if row:
                    # Extract data from row tuple
                    (
                        exec_id, status, started_at, completed_at,
                        outputs, errors, error_details, progress
                    ) = row
                    
                    current_status = status if isinstance(status, str) else status.value
                    current_progress = progress or {}

                    # Send update if status or progress changed
                    if (
                        current_status != last_status
                        or current_progress != last_progress
                    ):
                        yield f"data: {json.dumps({
                            'type': 'update',
                            'execution_id': execution_id,
                            'status': current_status,
                            'started_at': started_at.isoformat() if started_at else None,
                            'completed_at': completed_at.isoformat() if completed_at else None,
                            'outputs': outputs,
                            'errors': errors,
                            'error_details': error_details,
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
                            'started_at': started_at.isoformat() if started_at else None,
                            'completed_at': completed_at.isoformat() if completed_at else None,
                            'outputs': outputs,
                            'errors': errors,
                            'error_details': error_details,
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
        error_details=execution.error_details,
        progress=execution.progress or {},
        storage_keys=execution.storage_keys,
        started_at=execution.started_at.isoformat(),
        completed_at=(
            execution.completed_at.isoformat() if execution.completed_at else None
        ),
    )


@router.get("/executions/{execution_id}/stream/{node_name}")
async def stream_node_output(
    execution_id: str,
    node_name: str,
    current_user: User = Depends(get_current_user_sse),
    session: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """Stream real-time output from a specific node (e.g., Python node stdout/stderr)"""
    logger.info(f"Streaming output for node {node_name} in execution {execution_id}")

    async def event_generator():
        """Generate SSE events for node output streaming"""
        try:
            # Verify user owns this execution
            result = await session.execute(
                select(Execution)
                .where(Execution.id == execution_id)
                .where(Execution.user_id == current_user.id)
            )
            execution = result.scalar_one_or_none()
            
            if not execution:
                yield f"data: {json.dumps({
                    'type': 'error',
                    'message': 'Execution not found'
                })}\n\n"
                return
            
            # Send initial state
            if execution.progress and node_name in execution.progress:
                node_progress = execution.progress[node_name]
                if isinstance(node_progress, dict) and "output" in node_progress:
                    yield f"data: {json.dumps({
                        'type': 'initial',
                        'node_name': node_name,
                        'output': node_progress['output']
                    })}\n\n"
            
            # Poll for updates
            last_output = {"stdout": "", "stderr": ""}
            poll_count = 0
            max_polls = 300  # 10 minutes maximum for long-running nodes
            
            while poll_count < max_polls:
                try:
                    async with async_session() as session:
                        result = await session.execute(
                            select(Execution.progress, Execution.status)
                            .where(Execution.id == execution_id)
                        )
                        row = result.one_or_none()
                        
                        if row:
                            progress, status = row
                            
                            # Check if node has output
                            if progress and node_name in progress:
                                node_progress = progress[node_name]
                                
                                if isinstance(node_progress, dict):
                                    # Check for streaming output
                                    if "output" in node_progress:
                                        current_output = node_progress["output"]
                                        
                                        # Send new stdout
                                        if current_output.get("stdout", "") != last_output["stdout"]:
                                            new_stdout = current_output["stdout"][len(last_output["stdout"]):]
                                            if new_stdout:
                                                yield f"data: {json.dumps({
                                                    'type': 'stdout',
                                                    'text': new_stdout
                                                })}\n\n"
                                            last_output["stdout"] = current_output.get("stdout", "")
                                        
                                        # Send new stderr
                                        if current_output.get("stderr", "") != last_output["stderr"]:
                                            new_stderr = current_output["stderr"][len(last_output["stderr"]):]
                                            if new_stderr:
                                                yield f"data: {json.dumps({
                                                    'type': 'stderr',
                                                    'text': new_stderr
                                                })}\n\n"
                                            last_output["stderr"] = current_output.get("stderr", "")
                                    
                                    # Check if node completed
                                    node_status = node_progress.get("status")
                                    if node_status in ["completed", "failed"]:
                                        # Send final result if available
                                        if "streaming_output" in node_progress:
                                            yield f"data: {json.dumps({
                                                'type': 'complete',
                                                'status': node_status,
                                                'final_output': node_progress.get('streaming_output', {})
                                            })}\n\n"
                                        else:
                                            yield f"data: {json.dumps({
                                                'type': 'complete',
                                                'status': node_status
                                            })}\n\n"
                                        break
                            
                            # Check if execution completed
                            if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                                yield f"data: {json.dumps({
                                    'type': 'execution_complete',
                                    'status': status
                                })}\n\n"
                                break
                        
                        await session.close()
                    
                except Exception as e:
                    logger.error(f"Error streaming node output: {e}")
                    yield f"data: {json.dumps({
                        'type': 'error',
                        'message': str(e)
                    })}\n\n"
                    break
                
                await asyncio.sleep(0.5)  # Poll more frequently for real-time output
                poll_count += 1
            
            if poll_count >= max_polls:
                yield f"data: {json.dumps({
                    'type': 'timeout',
                    'message': 'Streaming timeout reached'
                })}\n\n"
        
        except Exception as e:
            logger.error(f"Error in node output stream: {e}")
            yield f"data: {json.dumps({
                'type': 'error',
                'message': str(e)
            })}\n\n"
    
    return EventSourceResponse(event_generator())
