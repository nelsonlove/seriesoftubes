"""FastAPI application for seriesoftubes"""

import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from seriesoftubes.api.auth_routes import router as auth_router
from seriesoftubes.api.docs_routes import router as docs_router
from seriesoftubes.api.execution_routes import router as execution_router
from seriesoftubes.api.workflow_routes import router as workflow_router
from seriesoftubes.db import init_db

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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(docs_router, prefix="/api")
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


@app.get("/api/schema")
async def get_workflow_schema() -> dict[str, Any]:
    """Get the workflow schema for validation"""
    # Load the workflow schema
    schema_path = Path(__file__).parent.parent / "schemas" / "workflow-schema.yaml"
    if not schema_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Workflow schema not found",
        )

    try:
        with open(schema_path) as f:
            schema = yaml.safe_load(f)
        return cast(dict[str, Any], schema)
    except Exception as e:
        logger.error(f"Failed to load workflow schema: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load workflow schema",
        ) from e


class WorkflowConvertRequest(BaseModel):
    """Convert workflow request"""

    content: str
    from_format: str = "yaml"  # yaml, json
    to_format: str = "json"  # yaml, json


class WorkflowConvertResponse(BaseModel):
    """Convert workflow response"""

    content: str
    format: str


@app.post("/api/convert", response_model=WorkflowConvertResponse)
async def convert_workflow(request: WorkflowConvertRequest) -> WorkflowConvertResponse:
    """Convert workflow between formats (YAML/JSON)"""
    try:
        # Parse from source format
        if request.from_format == "yaml":
            data = yaml.safe_load(request.content)
        elif request.from_format == "json":
            data = json.loads(request.content)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported source format: {request.from_format}",
            )

        # Convert to target format
        if request.to_format == "yaml":
            output = yaml.dump(data, default_flow_style=False, sort_keys=False)
        elif request.to_format == "json":
            output = json.dumps(data, indent=2)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported target format: {request.to_format}",
            )

        return WorkflowConvertResponse(
            content=output,
            format=request.to_format,
        )

    except yaml.YAMLError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid YAML: {e}",
        ) from e
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Conversion error: {e}",
        ) from e


# Documentation is served via /api/docs/ endpoints (see docs_routes.py)
