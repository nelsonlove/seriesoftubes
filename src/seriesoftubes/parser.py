"""YAML workflow parser and validator"""

import tempfile
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from seriesoftubes.models import (
    BaseNodeConfig,
    Node,
    NodeType,
    Workflow,
    WorkflowInput,
)


class WorkflowParseError(Exception):
    """Error parsing workflow YAML"""

    pass


def parse_node_config(
    _node_type: NodeType, config_data: dict[str, Any]
) -> dict[str, Any]:
    """Parse node configuration based on the node type"""
    # The Node model will handle the config validation automatically
    # based on the node type, so we just return the raw config data
    # This will be validated when creating the Node instance
    return config_data


def parse_workflow_yaml(yaml_path: Path) -> Workflow:
    """Parse and validate a workflow YAML file"""
    try:
        with yaml_path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        msg = f"Invalid YAML: {e}"
        raise WorkflowParseError(msg) from e
    except OSError as e:
        msg = f"Cannot read file: {e}"
        raise WorkflowParseError(msg) from e

    if not isinstance(data, dict):
        msg = "Workflow must be a YAML object"
        raise WorkflowParseError(msg)

    try:
        # Parse inputs
        inputs = {}
        for name, input_def in data.get("inputs", {}).items():
            if isinstance(input_def, dict):
                inputs[name] = WorkflowInput(**input_def)
            else:
                # Simple format: just the type
                inputs[name] = WorkflowInput(
                    type=str(input_def), required=True, default=None
                )

        # Parse nodes
        nodes = {}
        for name, node_data in data.get("nodes", {}).items():
            node_type = NodeType(node_data.get("type"))
            config_data = node_data.get("config", {})
            config = parse_node_config(node_type, config_data)

            nodes[name] = Node(
                name=name,
                type=node_type,
                description=node_data.get("description"),
                depends_on=node_data.get("depends_on", []),
                config=cast(BaseNodeConfig, config),
            )

        # Create workflow
        workflow = Workflow(
            name=data.get("name", "unnamed"),
            version=data.get("version", "1.0"),
            description=data.get("description"),
            inputs=inputs,
            nodes=nodes,
            outputs=data.get("outputs", {}),
        )

        return workflow

    except ValidationError as e:
        msg = f"Validation error: {e}"
        raise WorkflowParseError(msg) from e
    except KeyError as e:
        msg = f"Missing required field: {e}"
        raise WorkflowParseError(msg) from e
    except ValueError as e:
        msg = f"Invalid value: {e}"
        raise WorkflowParseError(msg) from e


def topological_sort(workflow: Workflow) -> list[str]:
    """Perform topological sort on workflow nodes

    Returns:
        List of node names in execution order
    """
    nodes = workflow.nodes
    in_degree = {name: len(node.depends_on) for name, node in nodes.items()}
    queue = [name for name, degree in in_degree.items() if degree == 0]
    result = []

    while queue:
        # Take node with no dependencies
        current = queue.pop(0)
        result.append(current)

        # Find nodes that depend on current
        for name, node in nodes.items():
            if current in node.depends_on:
                in_degree[name] -= 1
                if in_degree[name] == 0:
                    queue.append(name)

    if len(result) != len(nodes):
        msg = "Workflow contains a cycle"
        raise WorkflowParseError(msg)

    return result


def validate_dag(workflow: Workflow) -> None:
    """Validate the workflow DAG structure"""
    nodes = workflow.nodes

    # Check all dependencies exist
    for node_name, node in nodes.items():
        for dep in node.depends_on:
            if dep not in nodes:
                msg = f"Node '{node_name}' depends on non-existent node '{dep}'"
                raise WorkflowParseError(msg)

    # Check for cycles using DFS
    visited = set()
    rec_stack = set()

    def has_cycle(node_name: str) -> bool:
        visited.add(node_name)
        rec_stack.add(node_name)

        for dep in nodes[node_name].depends_on:
            if dep not in visited:
                if has_cycle(dep):
                    return True
            elif dep in rec_stack:
                return True

        rec_stack.remove(node_name)
        return False

    for node_name in nodes:
        if node_name not in visited:
            if has_cycle(node_name):
                msg = f"Workflow contains a cycle involving node '{node_name}'"
                raise WorkflowParseError(msg)

    # Additional validation for specific node types can be added here
    # For now, basic DAG validation is sufficient


class WorkflowParser:
    """Parser for workflow YAML files"""

    def parse_file(self, file_path: str | Path) -> Workflow:
        """Parse a workflow from a YAML file"""
        if isinstance(file_path, str):
            file_path = Path(file_path)
        return parse_workflow_yaml(file_path)

    def parse_string(self, yaml_content: str) -> Workflow:
        """Parse a workflow from a YAML string"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            return self.parse_file(f.name)
