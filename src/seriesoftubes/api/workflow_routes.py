"""Workflow management routes for the API"""

import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from seriesoftubes.api.auth import get_current_active_user
from seriesoftubes.api.models import WorkflowInfo
from seriesoftubes.db import Workflow, User, get_db
from seriesoftubes.parser import parse_workflow_yaml

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowCreate(BaseModel):
    """Create workflow from YAML content"""

    name: str
    version: str
    description: str | None = None
    yaml_content: str
    is_public: bool = False


class WorkflowResponse(BaseModel):
    """Workflow response"""

    id: str
    name: str
    version: str
    description: str | None
    user_id: str
    username: str
    is_public: bool
    created_at: str
    updated_at: str


@router.get("", response_model=list[WorkflowResponse])
async def list_user_workflows(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    include_public: bool = True,
) -> list[WorkflowResponse]:
    """List workflows accessible to the current user"""
    # Build query
    if include_public:
        # User's workflows + public workflows
        result = await db.execute(
            select(Workflow)
            .options(selectinload(Workflow.user))
            .where((Workflow.user_id == current_user.id) | (Workflow.is_public == True))
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
    # Validate YAML
    try:
        # Parse YAML to validate structure
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(workflow_data.yaml_content)
            tmp_path = Path(tmp.name)

        try:
            parsed = parse_workflow_yaml(tmp_path)
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
            Workflow.name == workflow_data.name,
            Workflow.version == workflow_data.version,
            Workflow.user_id == current_user.id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow {workflow_data.name} v{workflow_data.version} already exists",
        )

    # Create workflow directory
    workflows_dir = Path.home() / ".seriesoftubes" / "workflows" / str(current_user.id)
    workflows_dir.mkdir(parents=True, exist_ok=True)

    workflow_dir = workflows_dir / f"{workflow_data.name}_{workflow_data.version}"
    workflow_dir.mkdir(exist_ok=True)

    # Save workflow.yaml
    workflow_file = workflow_dir / "workflow.yaml"
    workflow_file.write_text(workflow_data.yaml_content)

    # Create database entry
    workflow = Workflow(
        name=workflow_data.name,
        version=workflow_data.version,
        description=workflow_data.description or parsed.description,
        user_id=current_user.id,
        is_public=workflow_data.is_public,
        package_path=str(workflow_dir),
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
    )


@router.post("/upload", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def upload_workflow_package(
    file: UploadFile = File(..., description="Workflow package (ZIP file)"),
    is_public: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """Upload a workflow package (ZIP file containing workflow.yaml and assets)"""
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a ZIP archive",
        )

    # Read ZIP file
    content = await file.read()
    
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            # Check for workflow.yaml
            if "workflow.yaml" not in zf.namelist():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ZIP must contain workflow.yaml at root level",
                )

            # Extract workflow.yaml content
            yaml_content = zf.read("workflow.yaml").decode("utf-8")
            
            # Parse to get metadata
            yaml_data = yaml.safe_load(yaml_content)
            name = yaml_data.get("name", "untitled")
            version = yaml_data.get("version", "1.0.0")
            description = yaml_data.get("description")

            # Validate by parsing
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
                tmp.write(yaml_content)
                tmp_path = Path(tmp.name)

            try:
                parsed = parse_workflow_yaml(tmp_path)
                name = parsed.name
                version = parsed.version
                description = parsed.description
            finally:
                tmp_path.unlink()

            # Check if workflow exists
            result = await db.execute(
                select(Workflow).where(
                    Workflow.name == name,
                    Workflow.version == version,
                    Workflow.user_id == current_user.id,
                )
            )
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Workflow {name} v{version} already exists",
                )

            # Create workflow directory
            workflows_dir = Path.home() / ".seriesoftubes" / "workflows" / str(current_user.id)
            workflows_dir.mkdir(parents=True, exist_ok=True)

            workflow_dir = workflows_dir / f"{name}_{version}"
            if workflow_dir.exists():
                shutil.rmtree(workflow_dir)
            workflow_dir.mkdir()

            # Extract all files
            zf.extractall(workflow_dir)

            # Create database entry
            workflow = Workflow(
                name=name,
                version=version,
                description=description,
                user_id=current_user.id,
                is_public=is_public,
                package_path=str(workflow_dir),
                yaml_content=yaml_content,
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
            )

    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ZIP file",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing workflow package: {e}",
        ) from e


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    """Get a specific workflow"""
    result = await db.execute(
        select(Workflow)
        .options(selectinload(Workflow.user))
        .where(
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

    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        version=workflow.version,
        description=workflow.description,
        user_id=workflow.user_id,
        username=workflow.user.username,
        is_public=workflow.is_public,
        created_at=workflow.created_at.isoformat(),
        updated_at=workflow.updated_at.isoformat(),
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

    # Remove workflow directory
    workflow_dir = Path(workflow.package_path)
    if workflow_dir.exists():
        shutil.rmtree(workflow_dir)

    # Delete from database
    await db.delete(workflow)
    await db.commit()

    return {"message": f"Workflow {workflow.name} v{workflow.version} deleted"}