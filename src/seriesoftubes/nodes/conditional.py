"""Conditional node executor for branching logic"""

from typing import Any

import jinja2

from seriesoftubes.models import Node, ConditionalNodeConfig
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import RouteNodeInput, RouteNodeOutput


class ConditionalNodeExecutor(NodeExecutor):
    """Executor for conditional nodes that implement branching logic"""
    
    input_schema_class = RouteNodeInput
    output_schema_class = RouteNodeOutput

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute conditional node to evaluate conditions and return path
        
        Args:
            node: The conditional node to execute
            context: Execution context
            
        Returns:
            NodeResult with selected path and condition info
        """
        try:
            config = node.config
            if not isinstance(config, ConditionalNodeConfig):
                return NodeResult(
                    output=None,
                    success=False,
                    error="Invalid config type for conditional node",
                )

            # Get context data for template rendering
            template_data = self.prepare_context_data(node, context)
            
            # Set up Jinja2 environment for condition evaluation
            jinja_env = jinja2.Environment(
                loader=jinja2.BaseLoader(),
                undefined=jinja2.StrictUndefined,
            )

            selected_route = None
            condition_met = None
            
            # Evaluate conditions in order
            for condition in config.conditions:
                if condition.condition == "default" or condition.is_default:
                    # Default condition always matches
                    selected_route = condition.then
                    condition_met = "default"
                    break
                
                try:
                    # Render and evaluate the condition
                    condition_template = jinja_env.from_string(condition.condition)
                    result = condition_template.render(template_data)
                    
                    # Convert to boolean
                    if result.lower() in ('true', '1', 'yes'):
                        condition_result = True
                    elif result.lower() in ('false', '0', 'no', ''):
                        condition_result = False
                    else:
                        # Try to parse as boolean
                        condition_result = bool(result)
                    
                    if condition_result:
                        selected_route = condition.then
                        condition_met = condition.condition
                        break
                        
                except (jinja2.TemplateError, ValueError) as e:
                    return NodeResult(
                        output=None,
                        success=False,
                        error=f"Condition evaluation failed '{condition.condition}': {str(e)}",
                    )
            
            # If no condition matched and no default, use fallback
            if selected_route is None:
                if config.fallback:
                    selected_route = config.fallback
                    condition_met = "fallback"
                else:
                    return NodeResult(
                        output=None,
                        success=False,
                        error="No conditions matched and no fallback specified",
                    )

            return NodeResult(
                output={
                    "selected_route": selected_route,
                    "condition_met": condition_met,
                    "evaluated_conditions": len(config.conditions),
                },
                success=True,
                metadata={
                    "node_type": "conditional",
                    "condition": condition_met,
                    "route": selected_route,
                }
            )

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=f"Conditional node execution failed: {str(e)}",
            )