"""Filter node executor for conditional array filtering"""

from typing import Any

import jinja2

from seriesoftubes.models import Node, FilterNodeConfig
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import FilterNodeInput, FilterNodeOutput


class FilterNodeExecutor(NodeExecutor):
    """Executor for filter nodes that conditionally filter arrays"""
    
    input_schema_class = FilterNodeInput
    output_schema_class = FilterNodeOutput

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute filter node to filter array based on condition
        
        Args:
            node: The filter node to execute
            context: Execution context
            
        Returns:
            NodeResult with filtered array
        """
        try:
            config = node.config
            if not isinstance(config, FilterNodeConfig):
                return NodeResult(
                    output=None,
                    success=False,
                    error="Invalid config type for filter node",
                )

            # Get context data for template rendering
            template_data = self.prepare_context_data(node, context)
            
            # Check if we're in a parallel context with a single item
            if hasattr(context, 'is_parallel_context') and context.is_parallel_context:
                # We're processing a single item from a split
                # The item should be available in the context with the split's item_name
                split_item_name = None
                for dep in node.depends_on:
                    dep_output = context.get_output(dep)
                    if isinstance(dep_output, dict) and dep_output.get('parallel_data'):
                        split_item_name = dep_output.get('item_name', 'item')
                        break
                
                if split_item_name and split_item_name in template_data:
                    # We have a single item to check against the condition
                    item = template_data[split_item_name]
                    
                    # Evaluate condition for this single item
                    jinja_env = jinja2.Environment(
                        loader=jinja2.BaseLoader(),
                        undefined=jinja2.StrictUndefined,
                    )
                    
                    try:
                        condition_template = jinja_env.from_string(config.condition)
                        item_context = template_data.copy()
                        item_context['item'] = item
                        # Also make the item available under its split name
                        item_context[split_item_name] = item
                        
                        # Evaluate condition
                        result = condition_template.render(item_context)
                        if result.lower() in ('true', '1', 'yes'):
                            condition_met = True
                        elif result.lower() in ('false', '0', 'no', ''):
                            condition_met = False
                        else:
                            condition_met = bool(result)
                        
                        # Return the item if condition is met, None otherwise
                        return NodeResult(
                            output=item if condition_met else None,
                            success=True,
                            metadata={
                                "node_type": "filter",
                                "condition_met": condition_met,
                                "condition": config.condition,
                            }
                        )
                        
                    except (jinja2.TemplateError, ValueError) as e:
                        return NodeResult(
                            output=None,
                            success=False,
                            error=f"Filter condition evaluation failed: {str(e)}",
                        )
            
            # Get the array data to filter
            if config.field:
                if config.field in template_data:
                    array_data = template_data[config.field]
                else:
                    # Try to get from a specific node output
                    field_parts = config.field.split('.')
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
                # Filter the entire context if no field specified
                # Look for the first array in the context
                array_data = None
                for key, value in template_data.items():
                    if isinstance(value, list):
                        array_data = value
                        break
                
                if array_data is None:
                    return NodeResult(
                        output=None,
                        success=False,
                        error="No array found to filter in context",
                    )

            # Validate that we got an array
            if not isinstance(array_data, list):
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Data to filter is not an array (got {type(array_data).__name__})",
                )

            # Set up Jinja2 environment for condition evaluation
            jinja_env = jinja2.Environment(
                loader=jinja2.BaseLoader(),
                undefined=jinja2.StrictUndefined,
            )
            
            try:
                condition_template = jinja_env.from_string(config.condition)
            except jinja2.TemplateSyntaxError as e:
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Invalid condition template: {str(e)}",
                )

            # Filter the array
            filtered_items = []
            for item in array_data:
                # Create context for this item
                item_context = template_data.copy()
                item_context['item'] = item
                
                try:
                    # Evaluate condition
                    result = condition_template.render(item_context)
                    # Convert to boolean
                    if result.lower() in ('true', '1', 'yes'):
                        condition_met = True
                    elif result.lower() in ('false', '0', 'no', ''):
                        condition_met = False
                    else:
                        # Try to parse as boolean
                        condition_met = bool(result)
                    
                    if condition_met:
                        filtered_items.append(item)
                        
                except (jinja2.TemplateError, ValueError) as e:
                    # Skip items that cause template errors
                    continue

            return NodeResult(
                output=filtered_items,
                success=True,
                metadata={
                    "node_type": "filter",
                    "original_count": len(array_data),
                    "filtered_count": len(filtered_items),
                    "condition": config.condition,
                }
            )

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=f"Filter node execution failed: {str(e)}",
            )