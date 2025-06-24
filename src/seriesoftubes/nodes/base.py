"""Base node executor interface"""

import os
from abc import ABC, abstractmethod
from typing import Any, Protocol

from pydantic import BaseModel

from seriesoftubes.models import Node
from seriesoftubes.utils import wrap_context_data


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

        # Wrap the data to make dot notation safe in templates
        return wrap_context_data(data)
