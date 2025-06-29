"""Workflow management routes for the API"""

import asyncio
import io
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from seriesoftubes.api.auth import get_current_active_user
from seriesoftubes.db import Execution, User, Workflow, get_db
from seriesoftubes.db import ExecutionStatus as DBExecutionStatus
from seriesoftubes.parser import parse_workflow_yaml, validate_dag

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowCreate(BaseModel):
    """Create workflow from YAML content"""

    yaml_content: str
    is_public: bool = False


class WorkflowResponse(BaseModel):
    """Workflow response"""

    model_config = {"from_attributes": True}

    id: str
    name: str
    version: str
    description: str | None
    user_id: str
    username: str
    is_public: bool
    created_at: str
    updated_at: str
    yaml_content: str


class WorkflowUpdate(BaseModel):
    """Update workflow"""

    yaml_content: str
    is_public: bool | None = None


class WorkflowDetail(BaseModel):
    """Detailed workflow information"""

    id: str
    name: str
    version: str
    description: str | None
    user_id: str
    username: str
    is_public: bool
    created_at: str
    updated_at: str
    yaml_content: str
    parsed: dict[str, Any]  # Parsed workflow structure


@router.get("", response_model=list[WorkflowResponse])
async def list_user_workflows(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    *,
    include_public: bool = True,
) -> list[WorkflowResponse]:
    """List workflows accessible to the current user"""
    # Build query
    if include_public:
        # User's workflows + public workflows
        result = await db.execute(
            select(Workflow)
            .options(selectinload(Workflow.user))
            .where((Workflow.user_id == current_user.id) | (Workflow.is_public))
            .order_by(Workflow.updated_at.desc())
        )
    else:
        # Only user's workflows
        result = await db.execute(
            select(Workflow)
            .options(selectinload(Workflow.user))
            .where(Workflow.user_id == current_user.id)
            .order_by(Workflow.updated_at.desc())
        )

    workflows = result.scalars().all()

    return [
        WorkflowResponse(
            id=w.id,
            name=w.name,
            version=w.version,
            description=w.description,
            user_id=w.user_id,
            username=w.user.username,
            is_public=w.is_public,
            created_at=w.created_at.isoformat(),
            updated_at=w.updated_at.isoformat(),
            yaml_content=w.yaml_content,
        )
        for w in workflows
    ]


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_data: WorkflowCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """Create a new workflow from YAML content"""
    # Validate and parse YAML
    try:
        # Parse YAML to validate structure
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(workflow_data.yaml_content)
            tmp_path = Path(tmp.name)

        try:
            parsed = parse_workflow_yaml(tmp_path)
            # Also validate DAG structure
            validate_dag(parsed)
        finally:
            tmp_path.unlink()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid workflow YAML: {e}",
        ) from e

    # Check if workflow with same name/version exists for user
    result = await db.execute(
        select(Workflow).where(
            Workflow.name == parsed.name,
            Workflow.version == parsed.version,
            Workflow.user_id == current_user.id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow {parsed.name} v{parsed.version} already exists",
        )

    # Create database entry
    workflow = Workflow(
        name=parsed.name,
        version=parsed.version,
        description=parsed.description,
        user_id=current_user.id,
        is_public=workflow_data.is_public,
        package_path="",  # No longer using filesystem
        yaml_content=workflow_data.yaml_content,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        version=workflow.version,
        description=workflow.description,
        user_id=workflow.user_id,
        username=current_user.username,
        is_public=workflow.is_public,
        created_at=workflow.created_at.isoformat(),
        updated_at=workflow.updated_at.isoformat(),
        yaml_content=workflow.yaml_content,
    )


@router.post(
    "/upload", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED
)
async def upload_workflow(
    file: UploadFile = File(..., description="Workflow YAML file"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    *,
    is_public: bool = False,
) -> WorkflowResponse:
    """Upload a workflow YAML file"""
    if not file.filename or not (
        file.filename.endswith(".yaml") or file.filename.endswith(".yml")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a YAML file (.yaml or .yml)",
        )

    # Read file content
    content = await file.read()
    yaml_content = content.decode("utf-8")

    # Create workflow using the same logic as create_workflow
    workflow_data = WorkflowCreate(yaml_content=yaml_content, is_public=is_public)
    return await create_workflow(workflow_data, current_user, db)


@router.get("/{workflow_id}", response_model=WorkflowDetail)
async def get_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowDetail:
    """Get a specific workflow with parsed structure"""
    result = await db.execute(
        select(Workflow)
        .options(selectinload(Workflow.user))
        .where(
            Workflow.id == workflow_id,
            (Workflow.user_id == current_user.id) | (Workflow.is_public),
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Parse the workflow to get structure
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(workflow.yaml_content)
            tmp_path = Path(tmp.name)

        try:
            parsed = parse_workflow_yaml(tmp_path)
        finally:
            tmp_path.unlink()

        parsed_dict = {
            "name": parsed.name,
            "version": parsed.version,
            "description": parsed.description,
            "inputs": {
                name: {
                    "type": input_def.input_type,
                    "required": input_def.required,
                    "default": input_def.default,
                }
                for name, input_def in parsed.inputs.items()
            },
            "nodes": {
                name: {
                    "type": node.node_type.value,
                    "description": node.description,
                    "depends_on": node.depends_on,
                    "config": node.config.model_dump() if node.config else {},
                }
                for name, node in parsed.nodes.items()
            },
            "outputs": parsed.outputs,
        }
    except Exception as e:
        # If parsing fails, return empty structure
        parsed_dict = {"error": str(e)}

    return WorkflowDetail(
        id=workflow.id,
        name=workflow.name,
        version=workflow.version,
        description=workflow.description,
        user_id=workflow.user_id,
        username=workflow.user.username,
        is_public=workflow.is_public,
        created_at=workflow.created_at.isoformat(),
        updated_at=workflow.updated_at.isoformat(),
        yaml_content=workflow.yaml_content,
        parsed=parsed_dict,
    )


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    workflow_update: WorkflowUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """Update a workflow"""
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.user_id == current_user.id,
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Validate new YAML content
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(workflow_update.yaml_content)
            tmp_path = Path(tmp.name)

        try:
            parsed = parse_workflow_yaml(tmp_path)
            validate_dag(parsed)
        finally:
            tmp_path.unlink()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid workflow YAML: {e}",
        ) from e

    # Check if name/version changed and conflicts with existing
    if parsed.name != workflow.name or parsed.version != workflow.version:
        conflict = await db.execute(
            select(Workflow).where(
                Workflow.name == parsed.name,
                Workflow.version == parsed.version,
                Workflow.user_id == current_user.id,
                Workflow.id != workflow_id,
            )
        )
        if conflict.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Workflow {parsed.name} v{parsed.version} already exists",
            )

    # Update workflow
    workflow.name = parsed.name
    workflow.version = parsed.version
    workflow.description = parsed.description
    workflow.yaml_content = workflow_update.yaml_content
    workflow.updated_at = datetime.now(timezone.utc)
    if workflow_update.is_public is not None:
        workflow.is_public = workflow_update.is_public

    await db.commit()
    await db.refresh(workflow)

    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        version=workflow.version,
        description=workflow.description,
        user_id=workflow.user_id,
        username=current_user.username,
        is_public=workflow.is_public,
        created_at=workflow.created_at.isoformat(),
        updated_at=workflow.updated_at.isoformat(),
        yaml_content=workflow.yaml_content,
    )


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a workflow"""
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.user_id == current_user.id,
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Delete from database (cascade will handle executions)
    await db.delete(workflow)
    await db.commit()

    return {"message": f"Workflow {workflow.name} v{workflow.version} deleted"}


class WorkflowValidateRequest(BaseModel):
    """Validate workflow request"""

    yaml_content: str | None = None  # If provided, validate this YAML
    # Otherwise validate the workflow's current YAML


class WorkflowValidateResponse(BaseModel):
    """Validation response"""

    valid: bool
    errors: list[str] | None = None
    warnings: list[str] | None = None
    parsed_structure: dict[str, Any] | None = None


@router.post("/{workflow_id}/validate", response_model=WorkflowValidateResponse)
async def validate_workflow(
    workflow_id: str,
    request: WorkflowValidateRequest | None = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowValidateResponse:
    """Validate a workflow's structure and configuration"""
    # Get workflow
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            (Workflow.user_id == current_user.id) | (Workflow.is_public),
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Use provided YAML or workflow's current YAML
    yaml_content = (
        request.yaml_content
        if request and request.yaml_content
        else workflow.yaml_content
    )

    errors = []
    warnings = []
    parsed_structure = None

    try:
        # Parse YAML
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(yaml_content)
            tmp_path = Path(tmp.name)

        try:
            parsed = parse_workflow_yaml(tmp_path)
            # Validate DAG
            validate_dag(parsed)

            # Build parsed structure
            parsed_structure = {
                "name": parsed.name,
                "version": parsed.version,
                "description": parsed.description,
                "inputs": {
                    name: {
                        "type": input_def.input_type,
                        "required": input_def.required,
                        "default": input_def.default,
                    }
                    for name, input_def in parsed.inputs.items()
                },
                "nodes": {
                    name: {
                        "type": node.node_type.value,
                        "description": node.description,
                        "depends_on": node.depends_on,
                    }
                    for name, node in parsed.nodes.items()
                },
                "outputs": parsed.outputs,
            }

            # Add warnings for best practices
            if not parsed.description:
                warnings.append("Workflow should have a description")
            if len(parsed.nodes) == 0:
                warnings.append("Workflow has no nodes")

        finally:
            tmp_path.unlink()

    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML syntax: {e}")
    except Exception as e:
        errors.append(str(e))

    return WorkflowValidateResponse(
        valid=len(errors) == 0,
        errors=errors if errors else None,
        warnings=warnings if warnings else None,
        parsed_structure=parsed_structure,
    )


class WorkflowTestRequest(BaseModel):
    """Test workflow request"""

    inputs: dict[str, Any] = {}
    mock_responses: dict[str, Any] = {}  # Mock responses for external calls


class WorkflowTestResponse(BaseModel):
    """Test execution response"""

    execution_id: str
    status: str
    outputs: dict[str, Any] | None = None
    errors: dict[str, str] | None = None
    node_outputs: dict[str, Any] | None = None  # Individual node outputs


@router.post("/{workflow_id}/test", response_model=WorkflowTestResponse)
async def test_workflow(
    workflow_id: str,
    request: WorkflowTestRequest,  # noqa: ARG001
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowTestResponse:
    """Run a workflow in test mode with mocked external calls"""
    # Get workflow
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            (Workflow.user_id == current_user.id) | (Workflow.is_public),
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # TODO: Implement test execution with mocks
    # For now, return a placeholder response
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Test execution not yet implemented",
    )


@router.get("/{workflow_id}/download")
async def download_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    *,
    format: str = "yaml",  # yaml or tubes (zip)  # noqa: A002
) -> Response:
    """Download a workflow as YAML or .tubes package"""

    # Get workflow
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            (Workflow.user_id == current_user.id) | (Workflow.is_public),
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    if format == "yaml":
        # Return YAML content
        return Response(
            content=workflow.yaml_content,
            media_type="application/x-yaml",
            headers={
                "Content-Disposition": f'attachment; filename="{workflow.name}_v{workflow.version}.yaml"'
            },
        )
    elif format == "tubes":
        # Create ZIP package
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add workflow.yaml
            zf.writestr("workflow.yaml", workflow.yaml_content)
            # Add metadata
            metadata = {
                "name": workflow.name,
                "version": workflow.version,
                "description": workflow.description,
                "created_at": workflow.created_at.isoformat(),
                "updated_at": workflow.updated_at.isoformat(),
            }
            zf.writestr("metadata.json", json.dumps(metadata, indent=2))

        zip_buffer.seek(0)
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{workflow.name}_v{workflow.version}.tubes"'
            },
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format must be 'yaml' or 'tubes'",
        )


class WorkflowRunRequest(BaseModel):
    """Run workflow request"""

    inputs: dict[str, Any] = {}


class WorkflowRunResponse(BaseModel):
    """Run workflow response"""

    execution_id: str
    status: str
    message: str


@router.post("/{workflow_id}/run", response_model=WorkflowRunResponse)
async def run_workflow(
    workflow_id: str,
    request: WorkflowRunRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowRunResponse:
    """Execute a workflow"""

    # Get workflow
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            (Workflow.user_id == current_user.id) | (Workflow.is_public),
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Create execution in database
    execution = Execution(
        workflow_id=workflow.id,
        user_id=current_user.id,
        inputs=request.inputs,
        status=DBExecutionStatus.PENDING.value,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Start execution asynchronously
    async def run_and_update() -> None:
        """Run workflow and update database"""
        async with AsyncSession(db.bind) as session:
            try:
                # Update status to running
                await session.execute(
                    update(Execution)
                    .where(Execution.id == execution.id)
                    .values(status=DBExecutionStatus.RUNNING.value)
                )
                await session.commit()

                # Parse and run workflow from YAML content
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                ) as tmp:
                    tmp.write(workflow.yaml_content)
                    tmp_path = Path(tmp.name)

                try:
                    parsed = parse_workflow_yaml(tmp_path)

                    # Use database-connected progress tracking engine
                    from seriesoftubes.api.execution import (
                        DatabaseProgressTrackingEngine,
                    )

                    engine = DatabaseProgressTrackingEngine(execution.id, session, current_user.id)
                    context = await engine.execute(parsed, request.inputs)

                    # Prepare outputs from workflow context
                    outputs = {}
                    for output_name, node_name in parsed.outputs.items():
                        if node_name in context.outputs:
                            outputs[output_name] = context.outputs[node_name]

                    # Determine final status based on errors
                    final_status = (
                        DBExecutionStatus.COMPLETED.value
                        if not context.errors
                        else DBExecutionStatus.FAILED.value
                    )

                    # Update execution as completed/failed
                    execution_update = {
                        "status": final_status,
                        "outputs": outputs,
                        "errors": context.errors if context.errors else None,
                        "completed_at": datetime.now(timezone.utc),
                    }
                    
                    # Add storage keys if available
                    if hasattr(context, 'storage_keys') and context.storage_keys:
                        execution_update["storage_keys"] = context.storage_keys
                    
                    await session.execute(
                        update(Execution)
                        .where(Execution.id == execution.id)
                        .values(**execution_update)
                    )
                    await session.commit()

                finally:
                    tmp_path.unlink()

            except Exception as e:
                # Update execution as failed
                await session.execute(
                    update(Execution)
                    .where(Execution.id == execution.id)
                    .values(
                        status=DBExecutionStatus.FAILED.value,
                        errors={"error": str(e)},
                        completed_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

    # Start execution in background
    asyncio.create_task(run_and_update())  # noqa: RUF006

    return WorkflowRunResponse(
        execution_id=execution.id,
        status="started",
        message=f"Workflow execution started with ID: {execution.id}",
    )
