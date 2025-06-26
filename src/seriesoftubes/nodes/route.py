"""Route node executor implementation"""

from typing import Any

from jinja2 import Template
from pydantic import ValidationError

from seriesoftubes.models import Node, RouteNodeConfig
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import RouteNodeInput, RouteNodeOutput


class RouteNodeExecutor(NodeExecutor):
    """Executor for route/conditional nodes"""

    input_schema_class = RouteNodeInput
    output_schema_class = RouteNodeOutput

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

            # Always validate input when schema is defined
            input_data = {"context_data": context_data}
            
            try:
                validated_input = self.validate_input(input_data)
                context_data = validated_input["context_data"]
            except ValidationError as e:
                # Format validation errors for clarity
                error_details = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error["loc"])
                    error_details.append(f"  - {field}: {error['msg']}")
                
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Input validation failed for node '{node.name}':\n" + "\n".join(error_details),
                )

            # Evaluate each route condition
            selected_route = None
            for route in config.routes:
                if route.default:
                    # This is the default route, select it if no other matches
                    selected_route = route.to
                elif route.when:
                    # Evaluate the condition
                    if self._evaluate_condition(route.when, context_data):
                        output = {
                            "selected_route": route.to,
                            "condition_met": route.when,
                        }

                        # Always validate output when schema is defined
                        try:
                            output = self.validate_output(output)
                        except ValidationError as e:
                            # Format validation errors for clarity
                            error_details = []
                            for error in e.errors():
                                field = ".".join(str(x) for x in error["loc"])
                                error_details.append(f"  - {field}: {error['msg']}")
                            
                            return NodeResult(
                                output=None,
                                success=False,
                                error=f"Output validation failed for node '{node.name}':\n" + "\n".join(error_details),
                            )

                        return NodeResult(
                            output=output,
                            success=True,
                            metadata={
                                "selected_route": route.to,
                                "condition": route.when,
                            },
                        )

            # If we get here, use the default route
            if selected_route is None:
                return NodeResult(
                    output=None,
                    success=False,
                    error="No route matched and no default route defined",
                )

            output = {
                "selected_route": selected_route,
                "condition_met": "default",  # Default route has no condition
            }

            # Always validate output when schema is defined
            try:
                output = self.validate_output(output)
            except ValidationError as e:
                # Format validation errors for clarity
                error_details = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error["loc"])
                    error_details.append(f"  - {field}: {error['msg']}")
                
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Output validation failed for node '{node.name}':\n" + "\n".join(error_details),
                )

            return NodeResult(
                output=output,
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
