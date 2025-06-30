"""Data models for seriesoftubes"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Self


class NodeType(str, Enum):
    """Supported node types"""

    LLM = "llm"
    HTTP = "http"
    FILE = "file"  # New file ingestion node type
    PYTHON = "python"  # Python code execution node type
    SPLIT = "split"  # Split arrays into parallel processing streams
    AGGREGATE = "aggregate"  # Collect parallel results into single output
    FILTER = "filter"  # Filter arrays based on conditions
    TRANSFORM = "transform"  # Transform data structures
    JOIN = "join"  # Join multiple data sources
    FOREACH = "foreach"  # Execute subgraph for each item in array
    CONDITIONAL = "conditional"  # Enhanced conditional processing


class HTTPMethod(str, Enum):
    """HTTP methods"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class BaseNodeConfig(BaseModel):
    """Base configuration for all node types"""

    # Common fields for all nodes
    context: dict[str, str] | None = Field(
        None, description="Map of variable names to node names for context"
    )

    # Schema definitions for validation
    input_schema: dict[str, Any] | None = Field(
        None, description="Expected input schema for validation"
    )
    output_schema: dict[str, Any] | None = Field(
        None, description="Expected output schema for validation"
    )


class LLMNodeConfig(BaseNodeConfig):
    """Configuration for LLM nodes"""

    # Prompt configuration
    prompt: str | None = Field(None, description="Direct prompt text")
    prompt_template: str | None = Field(
        None, description="Path to Jinja2 prompt template"
    )

    # LLM settings
    model: str | None = Field(None, description="Override default model")
    temperature: float | None = Field(None, description="Override default temperature")

    # Structured extraction
    schema_definition: dict[str, Any] | None = Field(
        None, description="Schema for structured extraction", alias="schema"
    )

    @field_validator("schema_definition", mode="before")
    @classmethod
    def validate_schema(cls, v: Any) -> dict[str, Any] | None:
        """Ensure schema is a dict if provided"""
        if v is None:
            return None
        if not isinstance(v, dict):
            msg = "Schema must be a dictionary"
            raise ValueError(msg)
        return v


class HTTPNodeConfig(BaseNodeConfig):
    """Configuration for HTTP nodes"""

    url: str = Field(..., description="URL to call (supports Jinja2 templates)")
    method: HTTPMethod = Field(HTTPMethod.GET, description="HTTP method")
    headers: dict[str, str] | None = Field(None, description="HTTP headers")
    params: dict[str, Any] | None = Field(None, description="Query parameters")
    body: dict[str, Any] | None = Field(None, description="Request body (for POST/PUT)")
    timeout: int | None = Field(None, description="Request timeout in seconds")


class FileNodeConfig(BaseNodeConfig):
    """Configuration for file ingestion nodes"""

    # File selection
    path: str | None = Field(None, description="Single file path (supports Jinja2)")
    pattern: str | None = Field(None, description="Glob pattern for multiple files")

    # Storage configuration
    storage_type: str = Field(
        "local",
        description="Storage type: local (filesystem) or object (S3/MinIO)",
    )
    storage_prefix: str | None = Field(
        None,
        description="Storage prefix for object storage (e.g., 'user-uploads/', 'workflow-outputs/')",
    )

    # Write mode configuration
    mode: str = Field(
        "read",
        description="Mode: read (read files) or write (write output to storage)",
    )
    write_key: str | None = Field(
        None,
        description="Storage key for writing (supports Jinja2 templates)",
    )

    # Format and parsing
    format_type: str = Field(
        "auto",
        description=(
            "File format: auto, json, jsonl, csv, txt, yaml, pdf, docx, xlsx, html"
        ),
        alias="format",
    )
    encoding: str = Field("utf-8", description="File encoding")
    extract_text: bool = Field(
        default=True, description="Extract text from documents (PDF, DOCX, HTML)"
    )

    # Output structure
    output_mode: str = Field(
        "content",
        description="Output mode: content (single), list (records), dict (collection)",
    )
    merge: bool = Field(
        default=False, description="Merge multiple files into single output"
    )

    # Streaming options for large files
    stream: bool = Field(default=False, description="Stream large files in chunks")
    chunk_size: int = Field(1000, description="Rows per chunk for streaming")
    sample: float | None = Field(None, description="Sample fraction (0.0-1.0)")
    limit: int | None = Field(None, description="Limit number of records")

    # CSV specific
    delimiter: str = Field(",", description="CSV delimiter")
    has_header: bool = Field(default=True, description="CSV has header row")

    # Error handling
    skip_errors: bool = Field(default=False, description="Skip files/rows with errors")

    @model_validator(mode="after")
    def validate_paths(self) -> Self:
        """Ensure configuration is valid for the mode"""
        if self.mode == "read":
            if not self.path and not self.pattern:
                msg = "Either 'path' or 'pattern' must be provided for read mode"
                raise ValueError(msg)
            if self.path and self.pattern:
                msg = "Cannot specify both 'path' and 'pattern'"
                raise ValueError(msg)
        elif self.mode == "write":
            if not self.write_key:
                msg = "'write_key' must be provided for write mode"
                raise ValueError(msg)
            if self.path or self.pattern:
                msg = "'path' and 'pattern' are not used in write mode"
                raise ValueError(msg)
        return self


class PythonNodeConfig(BaseNodeConfig):
    """Configuration for Python execution nodes"""

    # Code specification
    code: str | None = Field(None, description="Inline Python code to execute")
    file: str | None = Field(None, description="Path to Python file (supports Jinja2)")
    function: str | None = Field(
        None, description="Function name to call if using file"
    )

    # Resource limits
    timeout: int = Field(30, description="Execution timeout in seconds")
    memory_limit: str = Field(
        "100MB", description="Memory limit (e.g., '100MB', '1GB')"
    )

    # Security settings
    allowed_imports: list[str] = Field(
        default_factory=list,
        description="List of allowed module imports (empty = no imports allowed)",
    )
    max_output_size: int = Field(
        10_000_000, description="Maximum output size in bytes (10MB default)"
    )
    security_level: str = Field(
        "normal",
        description="Security level: strict, normal, or trusted",
    )

    @model_validator(mode="after")
    def validate_code_source(self) -> Self:
        """Ensure either code or file is provided, not both"""
        if not self.code and not self.file:
            msg = "Either 'code' or 'file' must be provided"
            raise ValueError(msg)
        if self.code and self.file:
            msg = "Cannot specify both 'code' and 'file'"
            raise ValueError(msg)
        if self.file and not self.function:
            # If file is provided without function, we'll execute the whole file
            pass
        return self


class SplitNodeConfig(BaseNodeConfig):
    """Configuration for split nodes"""

    field: str = Field(..., description="Field containing array to split")
    item_name: str = Field(
        "item", description="Name for each item in downstream context"
    )


class AggregateNodeConfig(BaseNodeConfig):
    """Configuration for aggregate nodes"""

    mode: str = Field(
        "array",
        description="Aggregation mode: array, object, merge",
    )
    field: str | None = Field(
        None, description="Optional: extract specific field from each result"
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate aggregation mode"""
        valid_modes = {"array", "object", "merge"}
        if v not in valid_modes:
            msg = f"Mode must be one of: {', '.join(valid_modes)}"
            raise ValueError(msg)
        return v


class FilterNodeConfig(BaseNodeConfig):
    """Configuration for filter nodes"""

    condition: str = Field(..., description="Jinja2 condition expression")
    field: str | None = Field(
        None, description="Array field to filter (if not provided, filters root array)"
    )


class TransformNodeConfig(BaseNodeConfig):
    """Configuration for transform nodes"""

    template: dict[str, Any] | str = Field(
        ..., description="Jinja2 template for transforming each item"
    )
    field: str | None = Field(
        None,
        description="Array field to transform (if not provided, transforms root array)",
    )


class JoinType(str, Enum):
    """Join types"""

    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    OUTER = "outer"
    CROSS = "cross"
    MERGE = "merge"


class JoinNodeConfig(BaseNodeConfig):
    """Configuration for join nodes"""

    sources: dict[str, str] = Field(
        ..., description="Named data sources to join (name -> node.field)"
    )
    join_type: JoinType = Field(JoinType.MERGE, description="Type of join to perform")
    join_keys: dict[str, str] | None = Field(
        None,
        description="Join key mappings for inner/left joins (source1_key -> source2_key)",
    )


class ForEachNodeConfig(BaseNodeConfig):
    """Configuration for foreach nodes"""

    array_field: str = Field(..., description="Field containing array to iterate over")
    item_name: str = Field("item", description="Name for each item in subgraph context")
    subgraph_nodes: list[str] = Field(
        ..., description="List of node names to execute for each item"
    )
    parallel: bool = Field(
        default=True,
        description="Execute iterations in parallel (default) or sequentially",
    )
    collect_output: str | None = Field(
        None, description="Output field name to collect from each iteration"
    )


class ConditionalCondition(BaseModel):
    """A single condition in a conditional node"""

    condition: str | None = Field(
        None, description="Jinja2 condition expression (omit for default)"
    )
    then: str = Field(..., description="Target/output value if condition is true")
    is_default: bool = Field(
        default=False, description="Whether this is the default condition"
    )

    @model_validator(mode="after")
    def validate_condition(self) -> Self:
        """Ensure condition is provided unless this is a default"""
        if not self.is_default and not self.condition:
            msg = "Condition is required unless is_default is True"
            raise ValueError(msg)
        return self


class ConditionalNodeConfig(BaseNodeConfig):
    """Configuration for conditional nodes - replaces old ROUTE functionality"""

    conditions: list[ConditionalCondition] = Field(
        ..., description="List of conditions to evaluate in order"
    )
    fallback: str | None = Field(
        None, description="Fallback value if no conditions match and no default"
    )


class CacheConfig(BaseModel):
    """Cache configuration for a node"""
    
    enabled: bool | None = Field(
        None, 
        description="Override default cache behavior for this node type"
    )
    ttl: int | None = Field(
        None, 
        description="Time to live in seconds (overrides default)"
    )
    key_fields: list[str] | None = Field(
        None,
        description="Specific context fields to include in cache key"
    )


class Node(BaseModel):
    """A node in the workflow DAG"""
    
    model_config = {"populate_by_name": True}

    name: str = Field(..., description="Unique node name", pattern=r"^[a-zA-Z0-9_-]+$")
    description: str | None = Field(
        None, description="Human-readable description of what this node does"
    )
    node_type: NodeType = Field(..., description="Type of node", alias="type")
    depends_on: list[str] = Field(
        default_factory=list, description="List of node dependencies"
    )
    config: BaseNodeConfig = Field(..., description="Node-specific configuration")
    cache: CacheConfig | None = Field(
        None, description="Cache configuration for this node"
    )

    @field_validator("config", mode="before")
    @classmethod
    def validate_config_type(cls, v: Any, info: Any) -> BaseNodeConfig:
        """Validate and convert config based on node type"""
        if isinstance(v, BaseNodeConfig):
            return v

        # Get the node type from the values
        node_type = info.data.get("node_type") or info.data.get("type")

        if not isinstance(v, dict):
            msg = "Config must be a dictionary"
            raise ValueError(msg)

        # Convert to appropriate config type
        if node_type == NodeType.LLM:
            return LLMNodeConfig(**v)
        elif node_type == NodeType.HTTP:
            return HTTPNodeConfig(**v)
        elif node_type == NodeType.FILE:
            return FileNodeConfig(**v)
        elif node_type == NodeType.PYTHON:
            return PythonNodeConfig(**v)
        elif node_type == NodeType.SPLIT:
            return SplitNodeConfig(**v)
        elif node_type == NodeType.AGGREGATE:
            return AggregateNodeConfig(**v)
        elif node_type == NodeType.FILTER:
            return FilterNodeConfig(**v)
        elif node_type == NodeType.TRANSFORM:
            return TransformNodeConfig(**v)
        elif node_type == NodeType.JOIN:
            return JoinNodeConfig(**v)
        elif node_type == NodeType.FOREACH:
            return ForEachNodeConfig(**v)
        elif node_type == NodeType.CONDITIONAL:
            return ConditionalNodeConfig(**v)
        else:
            msg = f"Unknown node type: {node_type}"
            raise ValueError(msg)


class WorkflowInput(BaseModel):
    """Workflow input definition"""

    type: str = Field("string", description="Data type (string, number, boolean, etc)")
    required: bool = Field(default=True, description="Is this input required")
    default: Any | None = Field(None, description="Default value if not provided")
    description: str | None = Field(None, description="Input description")
    # Custom input type for UI rendering (e.g., 'file' for file picker)
    input_type: str | None = Field(None, description="Custom input type for UI rendering")

    @model_validator(mode="after")
    def validate_required_with_default(self) -> Self:
        """If a default is provided, the input is not required"""
        if self.default is not None and self.required:
            self.required = False
        return self


class Workflow(BaseModel):
    """Complete workflow definition"""

    name: str = Field(..., description="Workflow name")
    version: str = Field(..., description="Workflow version")
    description: str | None = Field(None, description="Workflow description")
    inputs: dict[str, WorkflowInput] = Field(
        default_factory=dict, description="Input definitions"
    )
    nodes: dict[str, Node] = Field(..., description="DAG nodes")
    outputs: dict[str, str] = Field(default_factory=dict, description="Output mappings")

    @field_validator("nodes", mode="before")
    @classmethod
    def set_node_names(cls, v: Any) -> dict[str, Node]:
        """Set node names from dict keys"""
        if not isinstance(v, dict):
            msg = "Nodes must be a dictionary"
            raise ValueError(msg)

        nodes = {}
        for name, node_data in v.items():
            if isinstance(node_data, Node):
                node_data.name = name
                nodes[name] = node_data
            elif isinstance(node_data, dict):
                node_data["name"] = name
                nodes[name] = Node(**node_data)
            else:
                msg = f"Invalid node data for {name}"
                raise ValueError(msg)

        return nodes
