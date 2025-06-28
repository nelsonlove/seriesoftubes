"""Transform node executor for data structure mapping"""

import json
from typing import Any

import jinja2

from seriesoftubes.models import Node, TransformNodeConfig
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import TransformNodeInput, TransformNodeOutput


class TransformNodeExecutor(NodeExecutor):
    """Executor for transform nodes that map/transform data structures"""

    input_schema_class = TransformNodeInput
    output_schema_class = TransformNodeOutput

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute transform node to map data structures

        Args:
            node: The transform node to execute
            context: Execution context

        Returns:
            NodeResult with transformed data
        """
        try:
            config = node.config
            if not isinstance(config, TransformNodeConfig):
                return NodeResult(
                    output=None,
                    success=False,
                    error="Invalid config type for transform node",
                )

            # Get context data for template rendering
            template_data = self.prepare_context_data(node, context)

            # Check if we're in a parallel execution context (processing single items)
            is_parallel = hasattr(context, "is_parallel_context") and context.is_parallel_context
            
            
            if is_parallel:
                # For ForEach contexts, we don't need to look for item data - it's already in the context
                # Just render the template with the current context
                jinja_env = jinja2.Environment(
                    loader=jinja2.BaseLoader(),
                    undefined=jinja2.StrictUndefined,
                    autoescape=True,
                )
                
                try:
                    if isinstance(config.template, dict):
                        # Template is a dict structure - transform each field
                        transformed_item = {}
                        for field_name, field_template in config.template.items():
                            if isinstance(field_template, str):
                                # Render template
                                template = jinja_env.from_string(field_template)
                                rendered_value = template.render(template_data)

                                # Try to parse as JSON if it looks like JSON
                                try:
                                    if rendered_value.strip().startswith(
                                        ("{", "[", '"')
                                    ) or rendered_value.strip() in (
                                        "true",
                                        "false",
                                        "null",
                                    ):
                                        transformed_item[field_name] = json.loads(rendered_value)
                                    # Try to convert to appropriate type
                                    elif rendered_value.isdigit():
                                        transformed_item[field_name] = int(rendered_value)
                                    elif rendered_value.replace(".", "").isdigit():
                                        transformed_item[field_name] = float(rendered_value)
                                    else:
                                        transformed_item[field_name] = rendered_value
                                except (json.JSONDecodeError, ValueError):
                                    transformed_item[field_name] = rendered_value
                            else:
                                # Non-string template values are used as-is
                                transformed_item[field_name] = field_template

                        return NodeResult(
                            output=transformed_item,
                            success=True,
                            metadata={"node_type": "transform", "parallel_execution": True},
                        )

                    elif isinstance(config.template, str):
                        # Template is a string - render with current context
                        try:
                            template = jinja_env.from_string(config.template)
                        except jinja2.TemplateSyntaxError as e:
                            return NodeResult(
                                output=None,
                                success=False,
                                error=f"Invalid template syntax: {e!s}",
                            )

                        try:
                            rendered_value = template.render(template_data)

                            # Try to parse as JSON
                            try:
                                parsed_value = json.loads(rendered_value)
                                return NodeResult(
                                    output=parsed_value,
                                    success=True,
                                    metadata={"node_type": "transform", "parallel_execution": True},
                                )
                            except json.JSONDecodeError:
                                return NodeResult(
                                    output=rendered_value,
                                    success=True,
                                    metadata={"node_type": "transform", "parallel_execution": True},
                                )

                        except jinja2.TemplateError as e:
                            return NodeResult(
                                output=None,
                                success=False,
                                error=f"Template error: {e!s}",
                            )
                    else:
                        return NodeResult(
                            output=None,
                            success=False,
                            error=f"Invalid template type: {type(config.template).__name__}",
                        )
                        
                except Exception as e:
                    return NodeResult(
                        output=None,
                        success=False,
                        error=f"Parallel transform failed: {e!s}",
                    )
            
            # Regular execution - get the array data to transform
            if config.field:
                if config.field in template_data:
                    array_data = template_data[config.field]
                else:
                    # Try to get from a specific node output
                    field_parts = config.field.split(".")
                    if len(field_parts) == 2:
                        node_name, field_name = field_parts
                        node_output = context.get_output(node_name)
                        if isinstance(node_output, dict) and field_name in node_output:
                            array_data = node_output[field_name]
                        else:
                            return NodeResult(
                                output=None,
                                success=False,
                                error=f"Field '{field_name}' not found in output of node '{node_name}'",
                            )
                    else:
                        return NodeResult(
                            output=None,
                            success=False,
                            error=f"Field '{config.field}' not found in context",
                        )
            else:
                # Transform the first array found in context
                array_data = None
                for _key, value in template_data.items():
                    if isinstance(value, list):
                        array_data = value
                        break

                if array_data is None:
                    return NodeResult(
                        output=None,
                        success=False,
                        error="No array found to transform in context",
                    )

            # Validate that we got an array
            if not isinstance(array_data, list):
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Data to transform is not an array (got {type(array_data).__name__})",
                )

            # Set up Jinja2 environment for template rendering
            jinja_env = jinja2.Environment(
                loader=jinja2.BaseLoader(),
                undefined=jinja2.StrictUndefined,
                autoescape=True,
            )

            # Handle different template types
            if isinstance(config.template, dict):
                # Template is a dict structure - transform each field
                transformed_items = []
                for item in array_data:
                    # Skip None items (filtered out items)
                    if item is None:
                        continue

                    # Create context for this item
                    item_context = template_data.copy()
                    item_context["item"] = item

                    try:
                        transformed_item = {}
                        for field_name, field_template in config.template.items():
                            if isinstance(field_template, str):
                                # Render template
                                template = jinja_env.from_string(field_template)
                                rendered_value = template.render(item_context)

                                # Try to parse as JSON if it looks like JSON
                                try:
                                    if rendered_value.strip().startswith(
                                        ("{", "[", '"')
                                    ) or rendered_value.strip() in (
                                        "true",
                                        "false",
                                        "null",
                                    ):
                                        transformed_item[field_name] = json.loads(
                                            rendered_value
                                        )
                                    # Try to convert to appropriate type
                                    elif rendered_value.isdigit():
                                        transformed_item[field_name] = int(
                                            rendered_value
                                        )
                                    elif rendered_value.replace(".", "").isdigit():
                                        transformed_item[field_name] = float(
                                            rendered_value
                                        )
                                    else:
                                        transformed_item[field_name] = rendered_value
                                except (json.JSONDecodeError, ValueError):
                                    transformed_item[field_name] = rendered_value
                            else:
                                # Non-string template values are used as-is
                                transformed_item[field_name] = field_template

                        transformed_items.append(transformed_item)

                    except jinja2.TemplateError as e:
                        return NodeResult(
                            output=None,
                            success=False,
                            error=f"Template error for item {item}: {e!s}",
                        )

            elif isinstance(config.template, str):
                # Template is a string - render for each item
                try:
                    template = jinja_env.from_string(config.template)
                except jinja2.TemplateSyntaxError as e:
                    return NodeResult(
                        output=None,
                        success=False,
                        error=f"Invalid template syntax: {e!s}",
                    )

                string_transformed_items: list[Any] = []
                for item in array_data:
                    # Skip None items (filtered out items)
                    if item is None:
                        continue

                    # Create context for this item
                    item_context = template_data.copy()
                    item_context["item"] = item

                    try:
                        rendered_value = template.render(item_context)

                        # Try to parse as JSON
                        try:
                            parsed_value = json.loads(rendered_value)
                            string_transformed_items.append(parsed_value)
                        except json.JSONDecodeError:
                            string_transformed_items.append(rendered_value)

                    except jinja2.TemplateError as e:
                        return NodeResult(
                            output=None,
                            success=False,
                            error=f"Template error for item {item}: {e!s}",
                        )
            else:
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Invalid template type: {type(config.template).__name__}",
                )

            return NodeResult(
                output=(
                    transformed_items
                    if isinstance(config.template, dict)
                    else string_transformed_items
                ),
                success=True,
                metadata={
                    "node_type": "transform",
                    "original_count": len(array_data),
                    "transformed_count": len(
                        transformed_items
                        if isinstance(config.template, dict)
                        else string_transformed_items
                    ),
                },
            )

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=f"Transform node execution failed: {e!s}",
            )

