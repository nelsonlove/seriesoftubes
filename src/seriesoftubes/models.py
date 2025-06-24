"""Data models for seriesoftubes"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Self


class NodeType(str, Enum):
    """Supported node types"""

    LLM = "llm"
    HTTP = "http"
    ROUTE = "route"
    FILE = "file"  # New file ingestion node type
    PYTHON = "python"  # Python code execution node type


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


class RouteConfig(BaseModel):
    """Configuration for a single route"""

    when: str | None = Field(None, description="Condition expression")
    to: str = Field(..., description="Target node name")
    default: bool = Field(False, description="Is this the default route")


class RouteNodeConfig(BaseNodeConfig):
    """Configuration for route/conditional nodes"""

    routes: list[RouteConfig] = Field(..., description="List of routing rules")


class FileNodeConfig(BaseNodeConfig):
    """Configuration for file ingestion nodes"""

    # File selection
    path: str | None = Field(None, description="Single file path (supports Jinja2)")
    pattern: str | None = Field(None, description="Glob pattern for multiple files")

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
        True, description="Extract text from documents (PDF, DOCX, HTML)"
    )

    # Output structure
    output_mode: str = Field(
        "content",
        description="Output mode: content (single), list (records), dict (collection)",
    )
    merge: bool = Field(False, description="Merge multiple files into single output")

    # Streaming options for large files
    stream: bool = Field(False, description="Stream large files in chunks")
    chunk_size: int = Field(1000, description="Rows per chunk for streaming")
    sample: float | None = Field(None, description="Sample fraction (0.0-1.0)")
    limit: int | None = Field(None, description="Limit number of records")

    # CSV specific
    delimiter: str = Field(",", description="CSV delimiter")
    has_header: bool = Field(True, description="CSV has header row")

    # Error handling
    skip_errors: bool = Field(False, description="Skip files/rows with errors")

    @model_validator(mode="after")
    def validate_paths(self) -> Self:
        """Ensure either path or pattern is provided"""
        if not self.path and not self.pattern:
            msg = "Either 'path' or 'pattern' must be provided"
            raise ValueError(msg)
        if self.path and self.pattern:
            msg = "Cannot specify both 'path' and 'pattern'"
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


class Node(BaseModel):
    """A node in the workflow DAG"""

    name: str = Field(..., description="Unique node name", pattern=r"^[a-zA-Z0-9_-]+$")
    description: str | None = Field(
        None, description="Human-readable description of what this node does"
    )
    node_type: NodeType = Field(..., description="Type of node", alias="type")
    depends_on: list[str] = Field(
        default_factory=list, description="List of node dependencies"
    )
    config: BaseNodeConfig = Field(..., description="Node-specific configuration")

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
        elif node_type == NodeType.ROUTE:
            return RouteNodeConfig(**v)
        elif node_type == NodeType.FILE:
            return FileNodeConfig(**v)
        elif node_type == NodeType.PYTHON:
            return PythonNodeConfig(**v)
        else:
            msg = f"Unknown node type: {node_type}"
            raise ValueError(msg)


class WorkflowInput(BaseModel):
    """Workflow input definition"""

    input_type: str = Field("string", description="Input type", alias="type")
    required: bool = Field(True, description="Is this input required")
    default: Any | None = Field(None, description="Default value if not provided")

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
