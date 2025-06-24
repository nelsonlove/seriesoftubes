"""Parse JSON Schema and generate documentation."""

from pathlib import Path
from typing import Any

import yaml


class PropertyDoc:
    """Documentation for a single property."""

    def __init__(self, name: str, schema: dict[str, Any], *, required: bool = False):
        self.name = name
        self.schema = schema
        self.required = required
        self.type = self._get_type()
        self.description = schema.get("description", "")
        self.default = schema.get("default")
        self.examples = schema.get("examples", [])
        self.enum = schema.get("enum", [])
        self.constraints = self._get_constraints()

    def _get_type(self) -> str:
        """Extract property type."""
        if "type" in self.schema:
            return str(self.schema["type"])
        elif "oneOf" in self.schema:
            # For inputs that can be string or object
            types = []
            for option in self.schema["oneOf"]:
                if "type" in option:
                    types.append(str(option["type"]))
            return " | ".join(types) if types else "mixed"
        return "any"

    def _get_constraints(self) -> dict[str, Any]:
        """Extract property constraints."""
        constraints = {}
        for key in [
            "minimum",
            "maximum",
            "minLength",
            "maxLength",
            "pattern",
            "format",
        ]:
            if key in self.schema:
                constraints[key] = self.schema[key]
        return constraints


class NodeTypeDoc:
    """Documentation for a node type."""

    def __init__(self, name: str, config_schema: dict[str, Any]):
        self.name = name
        self.config_schema = config_schema
        self.properties = self._parse_properties()
        self.required_properties = [p for p in self.properties if p.required]
        self.optional_properties = [p for p in self.properties if not p.required]
        self.one_of_groups = self._parse_one_of_groups()

    def _parse_properties(self) -> list[PropertyDoc]:
        """Parse all properties from the schema."""
        properties = []
        props = self.config_schema.get("properties", {})
        required = self.config_schema.get("required", [])

        for prop_name, prop_schema in props.items():
            properties.append(
                PropertyDoc(prop_name, prop_schema, required=prop_name in required)
            )

        return properties

    def _parse_one_of_groups(self) -> list[list[str]]:
        """Parse oneOf constraints to find mutually exclusive property groups."""
        groups = []
        if "oneOf" in self.config_schema:
            for constraint in self.config_schema["oneOf"]:
                if "required" in constraint:
                    groups.append(constraint["required"])
        return groups


class SchemaDocGenerator:
    """Generate documentation from workflow schema."""

    def __init__(self, schema_path: Path):
        self.schema_path = schema_path
        self.schema = self._load_schema()
        self.node_configs = self._extract_node_configs()

    def _load_schema(self) -> dict[str, Any]:
        """Load and parse the YAML schema."""
        with open(self.schema_path) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}

    def _extract_node_configs(self) -> dict[str, dict[str, Any]]:
        """Extract node configuration schemas from definitions."""
        configs = {}
        definitions = self.schema.get("definitions", {})

        # Map node types to their config schemas
        node_mapping = {
            "llm": "llm_config",
            "http": "http_config",
            "route": "route_config",
            "file": "file_config",
            "python": "python_config",
        }

        for node_type, config_name in node_mapping.items():
            if config_name in definitions:
                configs[node_type] = definitions[config_name]

        return configs

    def get_node_types(self) -> list[str]:
        """Get list of available node types."""
        return list(self.node_configs.keys())

    def generate_node_documentation(self, node_type: str) -> str:
        """Generate markdown documentation for a specific node type."""
        if node_type not in self.node_configs:
            return f"# Error: Unknown node type '{node_type}'"

        config_schema = self.node_configs[node_type]
        node_doc = NodeTypeDoc(node_type, config_schema)

        # Build markdown
        lines = [
            f"# Node Type: `{node_type}`",
            "",
            self._get_node_description(node_type),
            "",
            "## Properties",
            "",
        ]

        # Required properties
        if node_doc.required_properties:
            lines.extend(
                [
                    "### Required Properties",
                    "",
                    "| Property | Type | Description |",
                    "|----------|------|-------------|",
                ]
            )

            for prop in node_doc.required_properties:
                desc = prop.description.replace("\n", " ")
                lines.append(f"| `{prop.name}` | {prop.type} | {desc} |")

            lines.append("")

        # Optional properties
        if node_doc.optional_properties:
            lines.extend(
                [
                    "### Optional Properties",
                    "",
                    "| Property | Type | Default | Description |",
                    "|----------|------|---------|-------------|",
                ]
            )

            for prop in node_doc.optional_properties:
                desc = prop.description.replace("\n", " ")
                default = f"`{prop.default}`" if prop.default is not None else "-"
                lines.append(f"| `{prop.name}` | {prop.type} | {default} | {desc} |")

            lines.append("")

        # Property constraints
        if node_doc.one_of_groups:
            lines.extend(
                [
                    "### Property Constraints",
                    "",
                    "You must provide ONE of the following property combinations:",
                    "",
                ]
            )

            for i, group in enumerate(node_doc.one_of_groups, 1):
                lines.append(f"{i}. " + " AND ".join(f"`{prop}`" for prop in group))

            lines.append("")

        # Property details
        lines.extend(["## Property Details", ""])

        for prop in node_doc.properties:
            lines.extend(self._generate_property_details(prop))

        # Examples
        lines.extend(self._generate_node_examples(node_type))

        return "\n".join(lines)

    def _get_node_description(self, node_type: str) -> str:
        """Get description for a node type."""
        descriptions = {
            "llm": "Execute Large Language Model (LLM) API calls with optional structured extraction.",
            "http": "Make HTTP API calls with authentication and templating support.",
            "route": "Conditionally route workflow execution based on data conditions.",
            "file": "Read and process files in various formats (JSON, CSV, YAML, PDF, etc.).",
            "python": "Execute Python code for data transformation and analysis.",
        }
        return descriptions.get(
            node_type, f"Process data using {node_type} operations."
        )

    def _generate_property_details(self, prop: PropertyDoc) -> list[str]:
        """Generate detailed documentation for a property."""
        lines = [f"### `{prop.name}`", ""]

        if prop.description:
            lines.extend([prop.description, ""])

        # Type and constraints
        type_info = [f"**Type:** `{prop.type}`"]

        if prop.required:
            type_info.append("**Required:** Yes")

        if prop.default is not None:
            type_info.append(f"**Default:** `{prop.default}`")

        if prop.enum:
            type_info.append(
                f"**Allowed values:** {', '.join(f'`{v}`' for v in prop.enum)}"
            )

        for constraint, value in prop.constraints.items():
            if constraint == "pattern":
                type_info.append(f"**Pattern:** `{value}`")
            elif constraint == "format":
                type_info.append(f"**Format:** {value}")
            else:
                type_info.append(f"**{constraint.title()}:** {value}")

        lines.extend([" | ".join(type_info), ""])

        # Examples
        if prop.examples:
            lines.extend(["**Examples:**", ""])
            for example in prop.examples:
                if isinstance(example, dict):
                    lines.append("```yaml")
                    for k, v in example.items():
                        lines.append(f"{k}: {v}")
                    lines.append("```")
                else:
                    lines.append(f"- `{example}`")
            lines.append("")

        return lines

    def _generate_node_examples(self, node_type: str) -> list[str]:
        """Generate example sections for a node type."""
        lines = ["", "## Examples", ""]

        # Add node-specific examples
        examples = self._get_node_examples(node_type)

        for i, (title, example) in enumerate(examples, 1):
            lines.extend(
                [f"### Example {i}: {title}", "", "```yaml", example.strip(), "```", ""]
            )

        return lines

    def _get_node_examples(self, node_type: str) -> list[tuple[str, str]]:
        """Get examples for each node type."""
        examples = {
            "llm": [
                (
                    "Basic prompt",
                    """
classify_company:
  type: llm
  config:
    prompt: "Classify this company: {{ company_name }}"
    model: gpt-4
    temperature: 0.7
""",
                ),
                (
                    "Structured extraction",
                    """
extract_data:
  type: llm
  depends_on: [fetch_data]
  config:
    prompt_template: prompts/extract.j2
    model: gpt-4
    context:
      data: fetch_data
    schema:
      type: object
      properties:
        revenue:
          type: number
        employees:
          type: integer
        industry:
          type: string
""",
                ),
            ],
            "http": [
                (
                    "Simple GET request",
                    """
fetch_api:
  type: http
  config:
    url: https://api.example.com/data
    method: GET
""",
                ),
                (
                    "POST with authentication",
                    """
create_record:
  type: http
  depends_on: [prepare_data]
  config:
    url: https://api.example.com/records
    method: POST
    headers:
      Content-Type: application/json
    auth:
      type: bearer
      token: "{{ env.API_TOKEN }}"
    body: "{{ prepare_data }}"
    context:
      prepare_data: prepare_data
""",
                ),
            ],
            "route": [
                (
                    "Conditional routing",
                    """
route_by_size:
  type: route
  depends_on: [analyze_company]
  config:
    context:
      company: analyze_company
    routes:
      - when: "{{ company.revenue > 1000000 }}"
        to: process_enterprise
      - when: "{{ company.employees < 50 }}"
        to: process_small_business
      - default: true
        to: process_standard
""",
                ),
            ],
            "file": [
                (
                    "Read JSON file",
                    """
load_data:
  type: file
  config:
    path: data/companies.json
    format: json
""",
                ),
                (
                    "Process CSV files",
                    """
load_csv_data:
  type: file
  config:
    pattern: data/*.csv
    format: csv
    merge: true
    skip_errors: true
""",
                ),
            ],
            "python": [
                (
                    "Data transformation",
                    """
transform_data:
  type: python
  depends_on: [load_data]
  config:
    code: |
      data = context['data']

      # Transform and filter
      result = {
          'total': len(data),
          'filtered': [d for d in data if d.get('active')],
          'summary': {
              'avg_revenue': sum(d.get('revenue', 0) for d in data) / len(data)
          }
      }

      return result
    context:
      data: load_data
""",
                ),
            ],
        }

        return examples.get(node_type, [])

    def generate_workflow_guide(self) -> str:
        """Generate a guide for workflow structure."""
        lines = [
            "# Workflow Structure Guide",
            "",
            "This guide explains the structure of SeriesOfTubes workflow files.",
            "",
            "## Basic Structure",
            "",
            "Every workflow is a YAML file with the following top-level properties:",
            "",
            "```yaml",
            "name: My Workflow Name",
            'version: "1.0.0"',
            "description: What this workflow does",
            "",
            "inputs:",
            "  # Define input parameters",
            "",
            "nodes:",
            "  # Define workflow nodes (DAG)",
            "",
            "outputs:",
            "  # Define what to return",
            "```",
            "",
            "## Workflow Properties",
            "",
        ]

        # Document top-level properties
        workflow_props = self.schema.get("properties", {})

        for prop_name in [
            "name",
            "version",
            "description",
            "inputs",
            "nodes",
            "outputs",
        ]:
            if prop_name in workflow_props:
                prop_schema = workflow_props[prop_name]
                required = prop_name in self.schema.get("required", [])

                lines.extend([f"### `{prop_name}`", ""])

                if "description" in prop_schema:
                    lines.extend([prop_schema["description"], ""])

                lines.append(f"**Type:** `{prop_schema.get('type', 'object')}`")
                lines.append(f"**Required:** {'Yes' if required else 'No'}")

                if "default" in prop_schema:
                    lines.append(f"**Default:** `{prop_schema['default']}`")

                if "pattern" in prop_schema:
                    lines.append(f"**Pattern:** `{prop_schema['pattern']}`")

                lines.extend(["", ""])

        # Add input types section
        lines.extend(
            [
                "## Input Types",
                "",
                "Workflow inputs support the following types:",
                "",
                "- `string` - Text values",
                "- `number` - Numeric values (float)",
                "- `integer` - Whole numbers",
                "- `boolean` - True/false values",
                "- `object` - JSON objects",
                "- `array` - Lists of values",
                "",
                "### Input Definition Examples",
                "",
                "```yaml",
                "inputs:",
                "  # Simple string input (shorthand)",
                "  company_name: string",
                "  ",
                "  # Detailed input with constraints",
                "  threshold:",
                "    type: number",
                "    required: false",
                "    default: 100",
                "    description: Revenue threshold",
                "  ",
                "  # Object input",
                "  config:",
                "    type: object",
                "    required: true",
                "```",
                "",
                "## Node Dependencies",
                "",
                "Nodes can depend on other nodes, creating a directed acyclic graph (DAG):",
                "",
                "```yaml",
                "nodes:",
                "  fetch_data:",
                "    type: http",
                "    config:",
                "      url: https://api.example.com/data",
                "  ",
                "  process_data:",
                "    type: python",
                "    depends_on: [fetch_data]  # Waits for fetch_data to complete",
                "    config:",
                "      context:",
                "        data: fetch_data  # Access output from fetch_data",
                "```",
                "",
                "## Context Mapping",
                "",
                "Nodes can access data from:",
                "- Previous node outputs via context mapping",
                "- Workflow inputs via `inputs` in context",
                "- Environment variables via Jinja2 templates",
                "",
                "```yaml",
                "process:",
                "  type: python",
                "  depends_on: [fetch_data, classify]",
                "  config:",
                "    context:",
                "      raw_data: fetch_data",
                "      classification: classify",
                "    code: |",
                "      # Access context variables",
                "      data = context['raw_data']",
                "      category = context['classification']",
                "      threshold = context['inputs']['threshold']",
                "```",
                "",
            ]
        )

        return "\n".join(lines)

    def generate_quick_reference(self) -> str:
        """Generate a quick reference guide."""
        lines = [
            "# SeriesOfTubes Quick Reference",
            "",
            "## Available Node Types",
            "",
            "| Node Type | Purpose | Key Properties |",
            "|-----------|---------|----------------|",
            "| `llm` | LLM API calls | `prompt`, `model`, `schema` |",
            "| `http` | HTTP requests | `url`, `method`, `headers` |",
            "| `route` | Conditional routing | `routes`, `when`, `to` |",
            "| `file` | File operations | `path`/`pattern`, `format` |",
            "| `python` | Python execution | `code`/`file`, `context` |",
            "",
            "## Common Patterns",
            "",
            "### LLM with Structured Output",
            "```yaml",
            "extract_info:",
            "  type: llm",
            "  config:",
            '    prompt: "Extract company info from: {{ text }}"',
            "    model: gpt-4",
            "    schema:",
            "      type: object",
            "      properties:",
            "        name: { type: string }",
            "        revenue: { type: number }",
            "```",
            "",
            "### API Call with Auth",
            "```yaml",
            "api_call:",
            "  type: http",
            "  config:",
            "    url: https://api.example.com/data",
            "    auth:",
            "      type: bearer",
            '      token: "{{ env.API_TOKEN }}"',
            "```",
            "",
            "### Conditional Routing",
            "```yaml",
            "route:",
            "  type: route",
            "  config:",
            "    routes:",
            '      - when: "{{ value > 100 }}"',
            "        to: high_value_path",
            "      - default: true",
            "        to: standard_path",
            "```",
            "",
            "### Python Data Processing",
            "```yaml",
            "analyze:",
            "  type: python",
            "  config:",
            "    code: |",
            "      data = context['data']",
            "      return {",
            "          'count': len(data),",
            "          'sum': sum(d['value'] for d in data)",
            "      }",
            "```",
            "",
            "## Jinja2 Template Variables",
            "",
            "- `{{ node_name }}` - Output from another node",
            "- `{{ inputs.param_name }}` - Workflow input parameter",
            "- `{{ env.VAR_NAME }}` - Environment variable",
            "- `{{ item }}` - Current item in loops",
            "",
            "## Tips",
            "",
            "1. Use `depends_on` to control execution order",
            "2. Map node outputs with `context` in config",
            "3. Use `prompt_template` for complex prompts",
            "4. Enable `skip_errors: true` for fault tolerance",
            "5. Use `schema` in LLM nodes for structured data",
            "",
        ]

        return "\n".join(lines)

    def generate_vscode_snippets(self) -> dict[str, Any]:
        """Generate VS Code snippets for workflow authoring."""
        snippets = {}

        # Workflow template
        snippets["SeriesOfTubes Workflow"] = {
            "prefix": "workflow",
            "body": [
                "name: ${1:Workflow Name}",
                'version: "1.0.0"',
                "description: ${2:What this workflow does}",
                "",
                "inputs:",
                "  ${3:input_name}:",
                "    type: ${4|string,number,boolean,object,array|}",
                "    required: ${5|true,false|}",
                "    description: ${6:Input description}",
                "",
                "nodes:",
                "  ${7:node_name}:",
                "    type: ${8|llm,http,route,file,python|}",
                "    config:",
                "      ${9}",
                "",
                "outputs:",
                "  ${10:output_name}: ${11:node_name}",
            ],
            "description": "Create a new SeriesOfTubes workflow",
        }

        # Node type snippets
        for node_type in self.get_node_types():
            snippets[f"{node_type.upper()} node"] = self._generate_node_snippet(
                node_type
            )

        # Input snippets
        snippets["Workflow input"] = {
            "prefix": "input",
            "body": [
                "${1:input_name}:",
                "  type: ${2|string,number,boolean,object,array|}",
                "  required: ${3|true,false|}",
                "  default: ${4}",
                "  description: ${5:Input description}",
            ],
            "description": "Add a workflow input parameter",
        }

        return snippets

    def _generate_node_snippet(self, node_type: str) -> dict[str, Any]:
        """Generate VS Code snippet for a specific node type."""
        bodies = {
            "llm": [
                "${1:node_name}:",
                "  type: llm",
                "  ${2:depends_on: [${3:dependency}]}",
                "  config:",
                '    prompt: "${4:Your prompt here}"',
                "    model: ${5|gpt-4,gpt-3.5-turbo,claude-3-opus-20240229|}",
                "    temperature: ${6:0.7}",
                "    ${7:context:}",
                "      ${8:data}: ${9:source_node}",
            ],
            "http": [
                "${1:node_name}:",
                "  type: http",
                "  ${2:depends_on: [${3:dependency}]}",
                "  config:",
                "    url: ${4:https://api.example.com/endpoint}",
                "    method: ${5|GET,POST,PUT,DELETE|}",
                "    ${6:headers:}",
                "      ${7:Content-Type}: ${8:application/json}",
                "    ${9:auth:}",
                "      ${10:type}: ${11|bearer,basic,api_key|}",
                '      ${12:token}: "${13:\\$\\{\\{ env.API_TOKEN \\}\\}}"',
            ],
            "route": [
                "${1:node_name}:",
                "  type: route",
                "  depends_on: [${2:dependency}]",
                "  config:",
                "    context:",
                "      ${3:data}: ${4:source_node}",
                "    routes:",
                '      - when: "${5:\\$\\{\\{ data.value > 100 \\}\\}}"',
                "        to: ${6:high_value_node}",
                "      - default: true",
                "        to: ${7:default_node}",
            ],
            "file": [
                "${1:node_name}:",
                "  type: file",
                "  config:",
                "    ${2|path,pattern|}: ${3:data/file.json}",
                "    format: ${4|auto,json,csv,yaml,txt,pdf|}",
                "    ${5:merge}: ${6|true,false|}",
                "    ${7:skip_errors}: ${8|true,false|}",
            ],
            "python": [
                "${1:node_name}:",
                "  type: python",
                "  ${2:depends_on: [${3:dependency}]}",
                "  config:",
                "    code: |",
                "      ${4:# Access context data}",
                "      data = context['${5:data}']",
                "      ",
                "      ${6:# Process data}",
                "      result = ${7:{'key': 'value'\\}}",
                "      ",
                "      return result",
                "    context:",
                "      ${5:data}: ${8:source_node}",
            ],
        }

        return {
            "prefix": f"{node_type}node",
            "body": bodies.get(node_type, ["${1:node_name}:", f"  type: {node_type}"]),
            "description": f"Add a {node_type} node to the workflow",
        }
