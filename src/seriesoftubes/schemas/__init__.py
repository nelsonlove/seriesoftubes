"""Schema definitions for SeriesOfTubes workflows."""

from abc import ABC
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

SCHEMA_DIR = Path(__file__).parent
WORKFLOW_SCHEMA_PATH = SCHEMA_DIR / "workflow-schema.yaml"

T = TypeVar("T", bound=BaseModel)


class NodeSchema(BaseModel, ABC):
    """Base class for all node schemas"""

    model_config = ConfigDict(
        # Allow extra fields by default for flexibility
        extra="allow",
        # Use enum values instead of names
        use_enum_values=True,
        # Validate on assignment
        validate_assignment=True,
    )


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

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that the URL is properly formatted"""
        if not v or not v.strip():
            msg = "URL cannot be empty"
            raise ValueError(msg)

        # Basic URL validation - must start with http:// or https://
        if not v.startswith(("http://", "https://")):
            msg = "URL must start with http:// or https://"
            raise ValueError(msg)

        # Could use HttpUrl for stricter validation, but that would require
        # converting back to string for the actual request
        return v


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
    condition_met: str = Field(
        ..., description="The condition that was met or 'default'"
    )


# File Node Schemas
class FileNodeInput(NodeInputSchema):
    """Input schema for file nodes"""

    path: str | None = Field(None, description="File path to read")
    pattern: str | None = Field(None, description="Glob pattern for multiple files")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str | None) -> str | None:
        """Validate that the path is not empty if provided"""
        if v is not None and not v.strip():
            msg = "Path cannot be empty"
            raise ValueError(msg)
        return v

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str | None) -> str | None:
        """Validate that the pattern is not empty if provided"""
        if v is not None and not v.strip():
            msg = "Pattern cannot be empty"
            raise ValueError(msg)
        return v


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


# Split Node Schemas
class SplitNodeInput(NodeInputSchema):
    """Input schema for split nodes"""

    array_data: list[Any] = Field(
        ..., description="Array to split into individual items"
    )


class SplitNodeOutput(NodeOutputSchema):
    """Output schema for split nodes"""

    # Split nodes don't have a traditional output - they create parallel executions
    # This output is returned for each item
    item: Any = Field(..., description="Individual item from the split array")
    index: int = Field(..., description="Index of this item in the original array")
    total: int = Field(..., description="Total number of items in the array")


# Aggregate Node Schemas
class AggregateNodeInput(NodeInputSchema):
    """Input schema for aggregate nodes"""

    items: list[Any] = Field(
        ..., description="Items to aggregate from parallel executions"
    )


class AggregateNodeOutput(NodeOutputSchema):
    """Output schema for aggregate nodes"""

    # Output structure depends on aggregation mode
    result: Any = Field(
        ..., description="Aggregated result (array, object, or merged data)"
    )
    count: int = Field(..., description="Number of items aggregated")


# Filter Node Schemas
class FilterNodeInput(NodeInputSchema):
    """Input schema for filter nodes"""

    items: list[Any] = Field(..., description="Array of items to filter")
    filter_context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context for filter conditions"
    )


class FilterNodeOutput(NodeOutputSchema):
    """Output schema for filter nodes"""

    filtered: list[Any] = Field(
        ..., description="Items that passed the filter condition"
    )
    removed_count: int = Field(..., description="Number of items filtered out")


# Transform Node Schemas
class TransformNodeInput(NodeInputSchema):
    """Input schema for transform nodes"""

    items: list[Any] = Field(..., description="Array of items to transform")
    transform_context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context for transformations"
    )


class TransformNodeOutput(NodeOutputSchema):
    """Output schema for transform nodes"""

    transformed: list[Any] = Field(..., description="Transformed items")
    transform_count: int = Field(..., description="Number of items transformed")


# Join Node Schemas
class JoinNodeInput(NodeInputSchema):
    """Input schema for join nodes"""

    sources: dict[str, Any] = Field(..., description="Named data sources to join")


class JoinNodeOutput(NodeOutputSchema):
    """Output schema for join nodes"""

    joined: Any = Field(..., description="Joined data (structure depends on join type)")
    source_counts: dict[str, int] = Field(
        ..., description="Number of items from each source"
    )


# Foreach Node Schemas
class ForeachNodeInput(NodeInputSchema):
    """Input schema for foreach nodes"""

    items: list[Any] = Field(..., description="Array of items to iterate over")
    foreach_context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context available to subgraph"
    )


class ForeachNodeOutput(NodeOutputSchema):
    """Output schema for foreach nodes"""

    results: list[Any] = Field(..., description="Collected results from all iterations")
    execution_count: int = Field(..., description="Number of iterations executed")


# Conditional Node Schemas (rename from RouteNode)
class ConditionalNodeInput(NodeInputSchema):
    """Input schema for conditional nodes"""

    context_data: dict[str, Any] = Field(
        ..., description="Data to evaluate conditions against"
    )


class ConditionalNodeOutput(NodeOutputSchema):
    """Output schema for conditional nodes"""

    selected_route: str = Field(..., description="The value from 'then' clause")
    condition_met: str = Field(
        ..., description="The condition that was met or 'default'"
    )
    evaluated_conditions: list[str] = Field(
        ..., description="List of conditions that were evaluated"
    )


# Node type to schema mapping
NODE_SCHEMAS: dict[str, dict[str, type[NodeSchema]]] = {
    "llm": {"input": LLMNodeInput, "output": LLMNodeOutput},
    "http": {"input": HTTPNodeInput, "output": HTTPNodeOutput},
    "route": {"input": RouteNodeInput, "output": RouteNodeOutput},  # Legacy
    "conditional": {"input": ConditionalNodeInput, "output": ConditionalNodeOutput},
    "file": {"input": FileNodeInput, "output": FileNodeOutput},
    "python": {"input": PythonNodeInput, "output": PythonNodeOutput},
    "split": {"input": SplitNodeInput, "output": SplitNodeOutput},
    "aggregate": {"input": AggregateNodeInput, "output": AggregateNodeOutput},
    "filter": {"input": FilterNodeInput, "output": FilterNodeOutput},
    "transform": {"input": TransformNodeInput, "output": TransformNodeOutput},
    "join": {"input": JoinNodeInput, "output": JoinNodeOutput},
    "foreach": {"input": ForeachNodeInput, "output": ForeachNodeOutput},
}
