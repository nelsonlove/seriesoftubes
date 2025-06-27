#!/usr/bin/env python
"""Generate JSON Schema from Pydantic models for IDE autocomplete in YAML files"""

import json
from pathlib import Path
from typing import Any, Dict

from seriesoftubes.models import (
    AggregateNodeConfig,
    ConditionalNodeConfig,
    FileNodeConfig,
    FilterNodeConfig,
    ForEachNodeConfig,
    HTTPNodeConfig,
    JoinNodeConfig,
    LLMNodeConfig,
    Node,
    NodeType,
    PythonNodeConfig,
    SplitNodeConfig,
    TransformNodeConfig,
    Workflow,
)
from seriesoftubes.schemas import NODE_SCHEMAS, NodeInputSchema, NodeOutputSchema


def generate_node_schema(node_type: str, config_class: type) -> dict[str, Any]:
    """Generate schema for a specific node type"""
    # Get the config schema
    config_schema = config_class.model_json_schema()

    # Get input/output schemas if available
    input_schema = None
    output_schema = None

    if node_type in NODE_SCHEMAS:
        if "input" in NODE_SCHEMAS[node_type]:
            input_schema = NODE_SCHEMAS[node_type]["input"].model_json_schema()
        if "output" in NODE_SCHEMAS[node_type]:
            output_schema = NODE_SCHEMAS[node_type]["output"].model_json_schema()

    # Build the complete node schema
    node_schema = {
        "type": "object",
        "properties": {
            "type": {"const": node_type},
            "config": config_schema,
            "depends_on": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of node names this node depends on",
            },
        },
        "required": ["type", "config"],
        "additionalProperties": False,
    }

    # Add input/output documentation
    if input_schema:
        node_schema["properties"]["__input_schema"] = {
            "description": "Expected input data structure",
            "readOnly": True,
            **input_schema,
        }

    if output_schema:
        node_schema["properties"]["__output_schema"] = {
            "description": "Output data structure",
            "readOnly": True,
            **output_schema,
        }

    return node_schema


def generate_workflow_schema() -> dict[str, Any]:
    """Generate complete workflow JSON schema"""

    # Node type to config class mapping
    node_configs = {
        NodeType.LLM: LLMNodeConfig,
        NodeType.HTTP: HTTPNodeConfig,
        NodeType.FILE: FileNodeConfig,
        NodeType.PYTHON: PythonNodeConfig,
        NodeType.SPLIT: SplitNodeConfig,
        NodeType.AGGREGATE: AggregateNodeConfig,
        NodeType.FILTER: FilterNodeConfig,
        NodeType.TRANSFORM: TransformNodeConfig,
        NodeType.JOIN: JoinNodeConfig,
        NodeType.FOREACH: ForEachNodeConfig,
        NodeType.CONDITIONAL: ConditionalNodeConfig,
    }

    # Generate schema for each node type
    node_schemas = {}
    for node_type, config_class in node_configs.items():
        node_schemas[node_type.value] = generate_node_schema(
            node_type.value, config_class
        )

    # Build the complete workflow schema
    workflow_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "SeriesOfTubes Workflow Schema",
        "description": "Schema for SeriesOfTubes workflow YAML files",
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Workflow name",
                "pattern": "^[a-z0-9-]+$",
            },
            "version": {
                "type": "string",
                "description": "Workflow version",
                "pattern": "^\\d+\\.\\d+\\.\\d+$",
            },
            "description": {
                "type": "string",
                "description": "Human-readable workflow description",
            },
            "inputs": {
                "type": "object",
                "description": "Input parameters for the workflow",
                "patternProperties": {
                    "^[a-zA-Z_][a-zA-Z0-9_]*$": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [
                                    "string",
                                    "number",
                                    "boolean",
                                    "array",
                                    "object",
                                ],
                            },
                            "description": {"type": "string"},
                            "required": {"type": "boolean"},
                            "default": {},
                            "example": {},
                        },
                        "required": ["type"],
                    }
                },
            },
            "nodes": {
                "type": "object",
                "description": "Workflow nodes (DAG)",
                "patternProperties": {
                    "^[a-zA-Z_][a-zA-Z0-9_]*$": {
                        "oneOf": [node_schemas[nt] for nt in node_schemas]
                    }
                },
                "additionalProperties": False,
            },
            "outputs": {
                "type": "object",
                "description": "Output mappings",
                "patternProperties": {
                    "^[a-zA-Z_][a-zA-Z0-9_]*$": {
                        "type": "string",
                        "description": "Node name or node.field reference",
                    }
                },
            },
        },
        "required": ["name", "version", "nodes"],
        "additionalProperties": False,
    }

    return workflow_schema


def generate_vscode_settings() -> dict[str, Any]:
    """Generate VS Code settings for YAML validation"""
    return {
        "yaml.schemas": {
            "./workflow-schema.json": [
                "*.workflow.yaml",
                "*.workflow.yml",
                "workflow.yaml",
                "workflow.yml",
            ]
        },
        "yaml.validate": True,
        "yaml.hover": True,
        "yaml.completion": True,
    }


def main():
    """Generate JSON schema files"""
    # Generate workflow schema
    workflow_schema = generate_workflow_schema()

    # Output directory
    output_dir = Path(__file__).parent.parent / "schemas"
    output_dir.mkdir(exist_ok=True)

    # Write workflow schema
    schema_path = output_dir / "workflow-schema.json"
    with open(schema_path, "w") as f:
        json.dump(workflow_schema, f, indent=2)
    print(f"Generated workflow schema: {schema_path}")

    # Generate individual node schemas for reference
    node_schemas_dir = output_dir / "nodes"
    node_schemas_dir.mkdir(exist_ok=True)

    node_configs = {
        NodeType.LLM: LLMNodeConfig,
        NodeType.HTTP: HTTPNodeConfig,
        NodeType.FILE: FileNodeConfig,
        NodeType.PYTHON: PythonNodeConfig,
        NodeType.SPLIT: SplitNodeConfig,
        NodeType.AGGREGATE: AggregateNodeConfig,
        NodeType.FILTER: FilterNodeConfig,
        NodeType.TRANSFORM: TransformNodeConfig,
        NodeType.JOIN: JoinNodeConfig,
        NodeType.FOREACH: ForEachNodeConfig,
        NodeType.CONDITIONAL: ConditionalNodeConfig,
    }

    for node_type, config_class in node_configs.items():
        node_schema = generate_node_schema(node_type.value, config_class)
        schema_path = node_schemas_dir / f"{node_type.value}-node.json"
        with open(schema_path, "w") as f:
            json.dump(node_schema, f, indent=2)
        print(f"Generated {node_type.value} node schema: {schema_path}")

    # Generate VS Code settings recommendation
    vscode_settings = generate_vscode_settings()
    vscode_path = output_dir / "vscode-settings.json"
    with open(vscode_path, "w") as f:
        json.dump(vscode_settings, f, indent=2)
    print(f"Generated VS Code settings: {vscode_path}")

    print("\nTo enable YAML autocomplete in VS Code:")
    print("1. Install the 'YAML' extension by Red Hat")
    print("2. Add the contents of vscode-settings.json to your .vscode/settings.json")
    print("3. Open any workflow YAML file and enjoy autocomplete!")


if __name__ == "__main__":
    main()
