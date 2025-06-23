"""Route node executor implementation"""

from typing import Any

from jinja2 import Template

from seriesoftubes.models import Node, RouteNodeConfig
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult


class RouteNodeExecutor(NodeExecutor):
    """Executor for route/conditional nodes"""

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute a route node to determine next path"""
        if not isinstance(node.config, RouteNodeConfig):
            return NodeResult(
                output=None,
                success=False,
                error=f"Invalid config type for route node: {type(node.config)}",
            )

        config = node.config

        try:
            # Prepare context for condition evaluation
            context_data = self.prepare_context_data(node, context)

            # Evaluate each route condition
            for route in config.routes:
                if route.default:
                    # This is the default route, select it if no other matches
                    selected_route = route.to
                elif route.when:
                    # Evaluate the condition
                    if self._evaluate_condition(route.when, context_data):
                        return NodeResult(
                            output=route.to,
                            success=True,
                            metadata={
                                "selected_route": route.to,
                                "condition": route.when,
                            },
                        )

            # If we get here, use the default route
            return NodeResult(
                output=selected_route,
                success=True,
                metadata={"selected_route": selected_route, "condition": "default"},
            )

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=str(e),
            )

    def _evaluate_condition(self, condition: str, context: dict[str, Any]) -> bool:
        """Evaluate a condition expression

        This is a simple implementation that evaluates the condition
        as a Jinja2 expression. In a production system, you might want
        to use a more restricted expression evaluator for security.
        """
        # Render the condition as a Jinja2 expression
        template = Template("{{ " + condition + " }}")
        result = template.render(**context)

        # Convert the result to boolean
        # Jinja2 will return 'True' or 'False' as strings
        return result.lower() == "true" or result == "1"
