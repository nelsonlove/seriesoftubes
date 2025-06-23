"""Core data models for seriesoftubes workflows"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator
from typing_extensions import Self


class NodeType(str, Enum):
    """Supported node types"""

    LLM = "llm"
    HTTP = "http"
    ROUTE = "route"


class LLMProvider(str, Enum):
    """Supported LLM providers"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class HTTPMethod(str, Enum):
    """HTTP methods"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class RouteCondition(BaseModel):
    """A routing condition"""

    when: str | None = Field(None, description="Condition expression")
    to: str = Field(..., description="Target node name")
    default: bool | None = Field(False, description="Is this the default route")

    @model_validator(mode="after")
    def validate_condition(self) -> Self:
        """Ensure either 'when' or 'default' is set, but not both"""
        if self.default and self.when:
            msg = "Cannot have both 'when' condition and 'default' flag"
            raise ValueError(msg)
        if not self.default and not self.when:
            msg = "Must have either 'when' condition or 'default' flag"
            raise ValueError(msg)
        return self


class BaseNodeConfig(BaseModel):
    """Base configuration for all node types"""

    context: dict[str, str] = Field(
        default_factory=dict,
        description="Context mapping from dependency outputs",
    )


class LLMNodeConfig(BaseNodeConfig):
    """Configuration for LLM nodes"""

    prompt: str | None = Field(None, description="Direct prompt text")
    prompt_template: str | None = Field(
        None, description="Path to Jinja2 template file"
    )
    schema_definition: dict[str, Any] | None = Field(
        None,
        description="Expected output schema for structured extraction",
        alias="schema",
    )
    model: str | None = Field(None, description="Override default model")
    temperature: float | None = Field(None, description="Override default temperature")

    @classmethod
    @field_validator("prompt", "prompt_template")
    def validate_prompt_source(cls, v: Any, info: ValidationInfo) -> Any:
        """Ensure exactly one prompt source is provided"""
        data = info.data
        prompt = data.get("prompt")
        template = data.get("prompt_template")

        # Only validate when we have all the data
        if info.field_name == "prompt_template" or (
            info.field_name == "prompt" and "prompt_template" in data
        ):
            if bool(prompt) == bool(template):
                msg = "Must provide exactly one of 'prompt' or 'prompt_template'"
                raise ValueError(msg)
        return v


class HTTPNodeConfig(BaseNodeConfig):
    """Configuration for HTTP nodes"""

    url: str = Field(..., description="URL to request")
    method: HTTPMethod = Field(HTTPMethod.GET, description="HTTP method")
    params: dict[str, Any] | None = Field(None, description="Query parameters")
    headers: dict[str, str] | None = Field(None, description="HTTP headers")
    body: dict[str, Any] | None = Field(None, description="Request body (JSON)")
    timeout: int | None = Field(None, description="Request timeout in seconds")


class RouteNodeConfig(BaseNodeConfig):
    """Configuration for routing nodes"""

    routes: list[RouteCondition] = Field(..., description="List of routing conditions")

    @classmethod
    @field_validator("routes")
    def validate_routes(cls, v: list[RouteCondition]) -> list[RouteCondition]:
        """Ensure exactly one default route"""
        defaults = [r for r in v if r.default]
        if len(defaults) > 1:
            msg = "Can only have one default route"
            raise ValueError(msg)
        if len(defaults) == 0:
            msg = "Must have exactly one default route"
            raise ValueError(msg)
        return v


class Node(BaseModel):
    """A workflow node"""

    name: str = Field(..., description="Unique node identifier")
    node_type: NodeType = Field(..., description="Node type", alias="type")
    depends_on: list[str] = Field(default_factory=list, description="Node dependencies")
    config: LLMNodeConfig | HTTPNodeConfig | RouteNodeConfig = Field(
        ..., description="Node-specific configuration"
    )

    @classmethod
    @field_validator("config")
    def validate_config_type(cls, v: Any, info: ValidationInfo) -> Any:
        """Ensure config matches node type"""
        data = info.data
        node_type = data.get("node_type") or data.get("type")
        if node_type == NodeType.LLM and not isinstance(v, LLMNodeConfig):
            msg = "LLM node requires LLMNodeConfig"
            raise ValueError(msg)
        elif node_type == NodeType.HTTP and not isinstance(v, HTTPNodeConfig):
            msg = "HTTP node requires HTTPNodeConfig"
            raise ValueError(msg)
        elif node_type == NodeType.ROUTE and not isinstance(v, RouteNodeConfig):
            msg = "Route node requires RouteNodeConfig"
            raise ValueError(msg)
        return v


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
    version: str = Field("1.0", description="Workflow version")
    description: str | None = Field(None, description="Workflow description")
    inputs: dict[str, WorkflowInput] = Field(
        default_factory=dict, description="Input definitions"
    )
    nodes: dict[str, Node] = Field(..., description="Workflow nodes")
    outputs: dict[str, str] = Field(
        default_factory=dict, description="Output mappings from nodes"
    )

    @classmethod
    @field_validator("nodes")
    def validate_node_names(cls, v: dict[str, Node]) -> dict[str, Node]:
        """Ensure node names in dict match node.name"""
        for name, node in v.items():
            if name != node.name:
                msg = f"Node key '{name}' doesn't match node name '{node.name}'"
                raise ValueError(msg)
        return v

    @classmethod
    @field_validator("outputs")
    def validate_outputs(
        cls, v: dict[str, str], info: ValidationInfo
    ) -> dict[str, str]:
        """Ensure output references exist"""
        data = info.data
        nodes = data.get("nodes", {})
        for output_name, node_name in v.items():
            if node_name not in nodes:
                msg = (
                    f"Output '{output_name}' references non-existent node '{node_name}'"
                )
                raise ValueError(msg)
        return v


class ExecutionConfig(BaseModel):
    """Runtime configuration from .tubes.yaml"""

    llm: dict[str, Any] = Field(default_factory=dict)
    http: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)
