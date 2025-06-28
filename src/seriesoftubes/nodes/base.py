"""Base node executor interface"""

import os
from abc import ABC, abstractmethod
from typing import Any, Protocol

from pydantic import BaseModel

from seriesoftubes.models import Node


class NodeResult(BaseModel):
    """Result from executing a node"""

    output: Any
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] | None = None


class NodeContext(Protocol):
    """Protocol for execution context passed to nodes"""

    def get_output(self, node_name: str) -> Any:
        """Get output from a previous node"""
        ...

    def get_input(self, input_name: str) -> Any:
        """Get workflow input value"""
        ...


class NodeExecutor(ABC):
    """Base class for node executors"""

    # Override these in subclasses to define schemas
    input_schema_class: type[BaseModel] | None = None
    output_schema_class: type[BaseModel] | None = None

    @abstractmethod
    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute a node and return its result

        Args:
            node: The node to execute
            context: Execution context with access to inputs and previous outputs

        Returns:
            NodeResult with output or error information
        """
        pass

    def prepare_context_data(self, node: Node, context: NodeContext) -> dict[str, Any]:
        """Prepare context data for template rendering

        Args:
            node: The node being executed
            context: Execution context

        Returns:
            Dictionary of context variables
        """
        data = {}

        # Add mapped context from node config
        if node.config.context:
            for var_name, node_name in node.config.context.items():
                data[var_name] = context.get_output(node_name)

        # Add inputs - get all inputs from the workflow context
        data["inputs"] = {}
        if hasattr(context, "inputs"):
            data["inputs"] = context.inputs

        # Add environment variables
        data["env"] = dict(os.environ)

        # Add split item data if available (for parallel execution contexts)
        if hasattr(context, "outputs"):
            for key, value in context.outputs.items():
                # Only add single values, not complex split metadata
                if not isinstance(value, dict) or not value.get("parallel_data"):
                    # Unwrap Python node schema results for easier template access
                    if (isinstance(value, dict) and "result" in value and len(value) == 1 
                        and isinstance(value["result"], (dict, list, str, int, float, bool, type(None)))):
                        data[key] = value["result"]
                    else:
                        data[key] = value

        # Return raw data - users should use bracket notation or filters in templates
        # e.g., data['items'] not data.items, or data|items not data.items()
        return data

    def validate_input(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate input data against the input schema

        Args:
            data: Input data to validate

        Returns:
            Validated data

        Raises:
            ValidationError: If validation fails
        """
        if self.input_schema_class and self.input_schema_class is not None:
            # ValidationError will be caught by the executor
            validated = self.input_schema_class(**data)
            return validated.model_dump()
        return data

    def validate_output(self, data: Any) -> Any:
        """Validate output data against the output schema

        Args:
            data: Output data to validate

        Returns:
            Validated data

        Raises:
            ValidationError: If validation fails
        """
        if self.output_schema_class and self.output_schema_class is not None:
            # Handle different output formats
            if isinstance(data, dict) and self.output_schema_class.model_fields:
                validated = self.output_schema_class(**data)
            else:
                # Wrap non-dict outputs
                validated = self.output_schema_class(result=data)
            return validated.model_dump()
        return data
