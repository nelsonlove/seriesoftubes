"""Schema definitions for SeriesOfTubes workflows."""

from abc import ABC
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, Field, ValidationError

SCHEMA_DIR = Path(__file__).parent
WORKFLOW_SCHEMA_PATH = SCHEMA_DIR / "workflow-schema.yaml"

T = TypeVar("T", bound=BaseModel)


class NodeSchema(BaseModel, ABC):
    """Base class for all node schemas"""

    class Config:
        """Pydantic config"""

        # Allow extra fields by default for flexibility
        extra = "allow"
        # Use enum values instead of names
        use_enum_values = True
        # Validate on assignment
        validate_assignment = True


class NodeInputSchema(NodeSchema):
    """Base class for node input schemas"""

    pass


class NodeOutputSchema(NodeSchema):
    """Base class for node output schemas"""

    pass


# Common schema components that can be reused
class BaseContext(BaseModel):
    """Base context available to all nodes"""

    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Workflow input values"
    )
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )


# LLM Node Schemas
class LLMNodeInput(NodeInputSchema):
    """Input schema for LLM nodes"""

    prompt: str = Field(..., description="The prompt to send to the LLM")
    context_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context data for template rendering",
    )


class LLMNodeOutput(NodeOutputSchema):
    """Output schema for LLM nodes"""

    response: str = Field(..., description="The LLM's text response")
    structured_output: dict[str, Any] | None = Field(
        None, description="Structured data if schema extraction was used"
    )
    model_used: str = Field(..., description="The model that was used")
    token_usage: dict[str, int] | None = Field(
        None, description="Token usage statistics"
    )


# HTTP Node Schemas
class HTTPNodeInput(NodeInputSchema):
    """Input schema for HTTP nodes"""

    url: str = Field(..., description="The URL to request")
    method: str = Field("GET", description="HTTP method")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    params: dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    body: dict[str, Any] | str | None = Field(None, description="Request body")


class HTTPNodeOutput(NodeOutputSchema):
    """Output schema for HTTP nodes"""

    status_code: int = Field(..., description="HTTP status code")
    headers: dict[str, str] = Field(..., description="Response headers")
    body: Any = Field(..., description="Response body")
    url: str = Field(..., description="The final URL (after redirects)")


# Route Node Schemas
class RouteNodeInput(NodeInputSchema):
    """Input schema for route nodes"""

    context_data: dict[str, Any] = Field(
        ..., description="Data to evaluate routing conditions against"
    )


class RouteNodeOutput(NodeOutputSchema):
    """Output schema for route nodes"""

    selected_route: str = Field(..., description="The node that was routed to")
    condition_met: str | None = Field(None, description="The condition that was met")


# File Node Schemas
class FileNodeInput(NodeInputSchema):
    """Input schema for file nodes"""

    path: str | None = Field(None, description="File path to read")
    pattern: str | None = Field(None, description="Glob pattern for multiple files")


class FileNodeOutput(NodeOutputSchema):
    """Output schema for file nodes - varies based on format and mode"""

    # The actual structure depends on:
    # - format (json, csv, txt, etc.)
    # - output_mode (content, list, dict)
    # This is a base that can be extended
    data: Any = Field(..., description="The loaded file data")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="File metadata (size, type, count, etc.)",
    )


# Python Node Schemas
class PythonNodeInput(NodeInputSchema):
    """Input schema for Python nodes"""

    context: dict[str, Any] = Field(
        ..., description="Context data available to the Python code"
    )


class PythonNodeOutput(NodeOutputSchema):
    """Output schema for Python nodes"""

    # Python nodes can return any JSON-serializable data
    result: Any = Field(..., description="The return value from the Python code")


# Schema validation utilities
class SchemaValidator:
    """Validates data against schemas"""

    @staticmethod
    def validate_input(data: dict[str, Any], schema_class: type[T]) -> T:
        """Validate input data against a schema"""
        try:
            return schema_class(**data)
        except ValidationError as e:
            # Re-raise with more context
            msg = f"Input validation failed for {schema_class.__name__}: {e}"
            raise ValidationError(msg) from e

    @staticmethod
    def validate_output(data: Any, schema_class: type[T]) -> T:
        """Validate output data against a schema"""
        try:
            if isinstance(data, dict):
                return schema_class(**data)
            else:
                # Try to construct from the raw data
                return schema_class(result=data)
        except ValidationError as e:
            # Re-raise with more context
            msg = f"Output validation failed for {schema_class.__name__}: {e}"
            raise ValidationError(msg) from e

    @staticmethod
    def validate_connection(
        output_schema: type[NodeOutputSchema],
        input_schema: type[NodeInputSchema],
        mapping: dict[str, str] | None = None,
    ) -> list[str]:
        """Validate that output from one node can feed into another

        Returns a list of validation errors, empty if valid
        """
        errors = []

        # Get required fields from input schema
        input_fields = input_schema.model_fields
        required_fields = {
            name: field for name, field in input_fields.items() if field.is_required()
        }

        # Get available fields from output schema
        output_fields = output_schema.model_fields

        # Check if required fields can be satisfied
        for field_name, _ in required_fields.items():
            mapped_name = mapping.get(field_name, field_name) if mapping else field_name

            if mapped_name not in output_fields:
                errors.append(
                    f"Required input field '{field_name}' cannot be satisfied by output"
                )
            else:
                # TODO: Check type compatibility
                pass

        return errors


# Node type to schema mapping
NODE_SCHEMAS = {
    "llm": {"input": LLMNodeInput, "output": LLMNodeOutput},
    "http": {"input": HTTPNodeInput, "output": HTTPNodeOutput},
    "route": {"input": RouteNodeInput, "output": RouteNodeOutput},
    "file": {"input": FileNodeInput, "output": FileNodeOutput},
    "python": {"input": PythonNodeInput, "output": PythonNodeOutput},
}
