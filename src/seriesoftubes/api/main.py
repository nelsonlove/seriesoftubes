"""FastAPI application for seriesoftubes"""

import asyncio
import json
import logging
import shutil
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from seriesoftubes.api.auth_routes import router as auth_router
from seriesoftubes.api.execution import execution_manager
from seriesoftubes.api.execution_routes import router as execution_router
from seriesoftubes.api.models import (
    ExecutionStatus,
    RawWorkflowResponse,
    RawWorkflowUpdate,
    WorkflowDetail,
    WorkflowInfo,
    WorkflowRunRequest,
    WorkflowRunResponse,
)
from seriesoftubes.api.workflow_routes import router as workflow_router
from seriesoftubes.db import init_db
from seriesoftubes.parser import WorkflowParseError, parse_workflow_yaml

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Initialize app on startup"""
    # Initialize database
    await init_db()
    logger.info("Database initialized")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down")


app = FastAPI(
    title="seriesoftubes API",
    description="LLM Workflow Orchestration Platform API",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(auth_router)
app.include_router(workflow_router)
app.include_router(execution_router)


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint"""
    return {"message": "Welcome to seriesoftubes API", "version": "0.1.0"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/workflows", response_model=list[WorkflowInfo])
async def list_workflows(directory: str = ".") -> list[WorkflowInfo]:
    """List available workflows in a directory"""
    workflows = []
    base_path = Path(directory)

    if not base_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")

    # Find all YAML files
    yaml_files = list(base_path.rglob("*.yaml")) + list(base_path.rglob("*.yml"))

    for yaml_file in yaml_files:
        try:
            workflow = parse_workflow_yaml(yaml_file)
            # Only include files that have nodes (actual workflows)
            if workflow.nodes:
                workflows.append(
                    WorkflowInfo(
                        name=workflow.name,
                        version=workflow.version,
                        description=workflow.description,
                        path=str(yaml_file),
                        inputs={
                            name: {
                                "type": input_def.input_type,
                                "required": input_def.required,
                                "default": input_def.default,
                            }
                            for name, input_def in workflow.inputs.items()
                        },
                    )
                )
        except Exception as e:
            # Skip invalid workflow files
            logger.debug(f"Skipping invalid workflow file {yaml_file}: {e}")
            continue

    return workflows


@app.get("/workflows/{workflow_path:path}", response_model=WorkflowDetail)
async def get_workflow(workflow_path: str) -> WorkflowDetail:
    """Get details about a specific workflow"""
    path = Path(workflow_path)

    if not path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        workflow = parse_workflow_yaml(path)
        return WorkflowDetail(
            path=str(path),
            workflow={
                "name": workflow.name,
                "version": workflow.version,
                "description": workflow.description,
                "inputs": {
                    name: {
                        "type": input_def.input_type,
                        "required": input_def.required,
                        "default": input_def.default,
                    }
                    for name, input_def in workflow.inputs.items()
                },
                "nodes": {
                    name: {
                        "type": node.node_type.value,
                        "description": node.description,
                        "depends_on": node.depends_on,
                        "config": node.config.model_dump() if node.config else {},
                    }
                    for name, node in workflow.nodes.items()
                },
                "outputs": workflow.outputs,
            },
        )
    except WorkflowParseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/workflows/{workflow_path:path}/raw", response_model=RawWorkflowResponse)
async def get_workflow_raw(workflow_path: str) -> RawWorkflowResponse:
    """Get raw YAML content of a workflow"""
    # Handle both absolute and relative paths
    path = Path(workflow_path)
    if not path.is_absolute():
        # If relative, resolve from current working directory
        path = Path.cwd() / path

    if not path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        content = path.read_text()
        stat = path.stat()
        return RawWorkflowResponse(
            content=content,
            path=str(path),
            modified=stat.st_mtime,
        )
    except Exception as e:
        logger.error(f"Failed to read workflow file {path}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to read workflow file"
        ) from e


@app.put("/workflows/{workflow_path:path}/raw", response_model=dict[str, Any])
async def update_workflow_raw(
    workflow_path: str, request: RawWorkflowUpdate
) -> dict[str, Any]:
    """Update raw YAML content of a workflow"""
    path = Path(workflow_path)

    if not path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Check for conflicts if expected_modified is provided
    if request.expected_modified is not None:
        current_modified = path.stat().st_mtime
        if (
            abs(current_modified - request.expected_modified) > 0.01
        ):  # Small tolerance for float comparison
            raise HTTPException(
                status_code=409,
                detail="File has been modified since it was loaded. Please reload and try again.",
            )

    # Validate the YAML content
    try:
        # First validate YAML syntax
        yaml.safe_load(request.content)

        # Then validate workflow structure by parsing
        # We need to save to a temp file to use parse_workflow_yaml
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(request.content)
            tmp_path = Path(tmp.name)

        try:
            workflow = parse_workflow_yaml(tmp_path)
        finally:
            tmp_path.unlink()  # Clean up temp file

    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML syntax: {e}") from e
    except WorkflowParseError as e:
        raise HTTPException(status_code=400, detail=f"Invalid workflow: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {e}") from e

    # Create backup
    backup_path = path.with_suffix(path.suffix + ".bak")
    try:
        shutil.copy2(path, backup_path)
    except Exception as e:
        logger.warning(f"Failed to create backup: {e}")

    # Save the new content
    try:
        path.write_text(request.content)
        new_stat = path.stat()
        return {
            "success": True,
            "path": str(path),
            "modified": new_stat.st_mtime,
            "workflow": {
                "name": workflow.name,
                "version": workflow.version,
            },
        }
    except Exception as e:
        # Try to restore from backup
        if backup_path.exists():
            try:
                shutil.copy2(backup_path, path)
            except Exception:  # noqa: S110
                pass
        raise HTTPException(
            status_code=500, detail=f"Failed to save workflow: {e}"
        ) from e


@app.post("/workflows/{workflow_path:path}/run", response_model=WorkflowRunResponse)
async def run_workflow(
    workflow_path: str, request: WorkflowRunRequest
) -> WorkflowRunResponse:
    """Run a workflow with the provided inputs"""
    path = Path(workflow_path)

    if not path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Start execution
    execution_id = await execution_manager.run_workflow(path, request.inputs)

    return WorkflowRunResponse(
        execution_id=execution_id,
        status="started",
        message=f"Workflow execution started with ID: {execution_id}",
    )


@app.get("/executions", response_model=list[ExecutionStatus])
async def list_executions() -> list[ExecutionStatus]:
    """List all workflow executions"""
    executions = execution_manager.list_executions()
    return [
        ExecutionStatus(
            execution_id=exec_data["id"],
            status=exec_data["status"],
            workflow_name=exec_data["workflow_name"],
            start_time=exec_data["start_time"],
            end_time=exec_data.get("end_time"),
            outputs=exec_data.get("outputs"),
            errors=exec_data.get("errors"),
            progress=exec_data.get("progress"),
        )
        for exec_data in executions
    ]


@app.get("/executions/{execution_id}", response_model=ExecutionStatus)
async def get_execution(execution_id: str) -> ExecutionStatus:
    """Get details about a specific execution"""
    exec_data = execution_manager.get_status(execution_id)

    if not exec_data:
        raise HTTPException(status_code=404, detail="Execution not found")

    return ExecutionStatus(
        execution_id=exec_data["id"],
        status=exec_data["status"],
        workflow_name=exec_data["workflow_name"],
        start_time=exec_data["start_time"],
        end_time=exec_data.get("end_time"),
        outputs=exec_data.get("outputs"),
        errors=exec_data.get("errors"),
        progress=exec_data.get("progress"),
    )


@app.get("/executions/{execution_id}/stream")
async def stream_execution(execution_id: str) -> EventSourceResponse:
    """Stream execution updates via Server-Sent Events"""
    exec_data = execution_manager.get_status(execution_id)

    if not exec_data:
        raise HTTPException(status_code=404, detail="Execution not found")

    async def event_generator() -> Any:
        """Generate SSE events for execution updates"""
        last_status = None
        last_progress = None

        while True:
            exec_data = execution_manager.get_status(execution_id)
            if not exec_data:
                break

            # Check for status changes
            current_status = exec_data["status"]
            current_progress = exec_data.get("progress", {})

            if current_status != last_status or current_progress != last_progress:
                yield {
                    "event": "update",
                    "data": json.dumps(
                        {
                            "execution_id": execution_id,
                            "status": current_status,
                            "progress": current_progress,
                            "outputs": exec_data.get("outputs"),
                            "errors": exec_data.get("errors"),
                        }
                    ),
                }
                last_status = current_status
                last_progress = current_progress

            # If execution is complete, send final event and close
            if current_status in ["completed", "failed"]:
                yield {
                    "event": "complete",
                    "data": json.dumps(
                        {
                            "execution_id": execution_id,
                            "status": current_status,
                            "outputs": exec_data.get("outputs"),
                            "errors": exec_data.get("errors"),
                        }
                    ),
                }
                break

            # Wait before checking again
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


# Mount documentation files
docs_path = Path(__file__).parent.parent.parent.parent / "docs"
if docs_path.exists():
    app.mount("/docs", StaticFiles(directory=str(docs_path)), name="docs")
    logger.info(f"Mounted documentation at /docs from {docs_path}")
else:
    logger.warning(f"Documentation directory not found at {docs_path}")
