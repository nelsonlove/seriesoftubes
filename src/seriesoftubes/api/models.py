"""API request/response models"""

from typing import Any

from pydantic import BaseModel, Field


class WorkflowRunRequest(BaseModel):
    """Request to run a workflow"""

    inputs: dict[str, Any] = Field(default_factory=dict, description="Workflow inputs")


class WorkflowRunResponse(BaseModel):
    """Response from running a workflow"""

    execution_id: str = Field(..., description="Unique execution ID")
    status: str = Field(..., description="Execution status")
    message: str = Field(..., description="Status message")


class WorkflowInfo(BaseModel):
    """Information about a workflow"""

    name: str = Field(..., description="Workflow name")
    version: str = Field(..., description="Workflow version")
    description: str | None = Field(None, description="Workflow description")
    path: str = Field(..., description="Workflow file path")
    inputs: dict[str, Any] = Field(..., description="Input definitions")


class WorkflowDetail(BaseModel):
    """Complete workflow details including structure"""

    path: str = Field(..., description="Workflow file path")
    workflow: dict[str, Any] = Field(..., description="Complete workflow definition")


class ExecutionStatus(BaseModel):
    """Execution status response"""

    execution_id: str = Field(..., description="Unique execution ID")
    status: str = Field(..., description="Current status")
    workflow_name: str = Field(..., description="Workflow name")
    start_time: str = Field(..., description="Start time ISO string")
    end_time: str | None = Field(None, description="End time ISO string")
    outputs: dict[str, Any] | None = Field(None, description="Workflow outputs")
    errors: dict[str, str] | None = Field(None, description="Errors by node")
    progress: dict[str, str] | None = Field(None, description="Node execution progress")


class ErrorResponse(BaseModel):
    """Error response"""

    detail: str = Field(..., description="Error message")
    code: str | None = Field(None, description="Error code")
