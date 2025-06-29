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

    def prepare_context_data(self, node: Node, context: NodeContext, unwrap_python_results: bool = True) -> dict[str, Any]:
        """Prepare context data for template rendering

        Args:
            node: The node being executed
            context: Execution context
            unwrap_python_results: Whether to unwrap Python node results for easier template access

        Returns:
            Dictionary of context variables
        """
        data = {}

        # Add mapped context from node config
        if node.config.context:
            for var_name, node_ref in node.config.context.items():
                # Handle nested attribute access (e.g., "extract_profile.structured_output")
                if "." in node_ref:
                    parts = node_ref.split(".", 1)
                    node_name = parts[0]
                    attr_path = parts[1]
                    
                    # Get the node output
                    node_output = context.get_output(node_name)
                    
                    # Navigate through nested attributes
                    if node_output is not None:
                        try:
                            # Split the attribute path and navigate through it
                            attrs = attr_path.split(".")
                            current = node_output
                            for attr in attrs:
                                if isinstance(current, dict):
                                    current = current.get(attr)
                                else:
                                    current = getattr(current, attr, None)
                                if current is None:
                                    break
                            data[var_name] = current
                        except (AttributeError, KeyError, TypeError):
                            # If we can't access the attribute, set None
                            data[var_name] = None
                    else:
                        data[var_name] = None
                else:
                    # Simple node reference without nested attributes
                    data[var_name] = context.get_output(node_ref)

        # Add inputs - get all inputs from the workflow context
        data["inputs"] = {}
        if hasattr(context, "inputs"):
            data["inputs"] = context.inputs

        # Add environment variables
        data["env"] = dict(os.environ)
        
        # Add execution metadata if available
        if hasattr(context, "execution_id"):
            data["execution_id"] = context.execution_id
        if hasattr(context, "workflow") and context.workflow:
            data["workflow_id"] = context.workflow.name
        if hasattr(context, "node") and hasattr(context.node, "name"):
            data["node_name"] = context.node.name
        elif hasattr(node, "name"):
            data["node_name"] = node.name

        # Add split item data if available (for parallel execution contexts)
        if hasattr(context, "outputs"):
            for key, value in context.outputs.items():
                # Only add single values, not complex split metadata
                if not isinstance(value, dict) or not value.get("parallel_data"):
                    # Unwrap Python node schema results for easier template access (but not for Python nodes themselves)
                    if (unwrap_python_results and isinstance(value, dict) and "result" in value and len(value) == 1 
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
