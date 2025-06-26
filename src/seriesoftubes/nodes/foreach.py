"""ForEach node executor for subgraph iteration"""

from seriesoftubes.models import ForEachNodeConfig, Node
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import ForeachNodeInput, ForeachNodeOutput


class ForEachNodeExecutor(NodeExecutor):
    """Executor for foreach nodes that execute subgraphs for each item in an array"""

    input_schema_class = ForeachNodeInput
    output_schema_class = ForeachNodeOutput

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute foreach node to iterate over array items

        Args:
            node: The foreach node to execute
            context: Execution context

        Returns:
            NodeResult with iteration results
        """
        try:
            config = node.config
            if not isinstance(config, ForEachNodeConfig):
                return NodeResult(
                    output=None,
                    success=False,
                    error="Invalid config type for foreach node",
                )

            # Get context data for template rendering
            template_data = self.prepare_context_data(node, context)

            # Get the array data to iterate over
            if config.array_field.startswith("inputs."):
                # Reference to workflow input
                input_name = config.array_field[7:]  # Remove "inputs." prefix
                if input_name in template_data.get("inputs", {}):
                    array_data = template_data["inputs"][input_name]
                else:
                    return NodeResult(
                        output=None,
                        success=False,
                        error=f"Input '{input_name}' not found",
                    )
            elif "." in config.array_field:
                # Reference to node output field
                node_name, field_name = config.array_field.split(".", 1)
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
                # Reference to entire node output
                node_output = context.get_output(config.array_field)
                if node_output is not None:
                    array_data = node_output
                else:
                    return NodeResult(
                        output=None,
                        success=False,
                        error=f"Output from node '{config.array_field}' not found",
                    )

            # Validate that we got an array
            if not isinstance(array_data, list):
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Data to iterate over is not an array (got {type(array_data).__name__})",
                )

            # For now, foreach will prepare iteration data for the execution engine
            # The actual subgraph execution would be handled by the engine
            iteration_results = []

            for i, item in enumerate(array_data):
                # Create iteration context
                iteration_context = {
                    "index": i,
                    "item": item,
                    config.item_name: item,
                    "is_first": i == 0,
                    "is_last": i == len(array_data) - 1,
                    "total_count": len(array_data),
                }

                # For now, just collect the items and context
                # In a full implementation, this would execute the subgraph
                iteration_result = {
                    "iteration_index": i,
                    "item_data": item,
                    "context": iteration_context,
                    "subgraph_nodes": config.subgraph_nodes,
                }

                iteration_results.append(iteration_result)

            # Return the iteration plan
            # NOTE: This is a simplified implementation
            # A full implementation would need engine support for subgraph execution
            return NodeResult(
                output={
                    "iteration_plan": iteration_results,
                    "total_iterations": len(array_data),
                    "item_name": config.item_name,
                    "subgraph_nodes": config.subgraph_nodes,
                    "array_field": config.array_field,
                },
                success=True,
                metadata={
                    "node_type": "foreach",
                    "iterations": len(array_data),
                    "subgraph_size": len(config.subgraph_nodes),
                },
            )

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=f"ForEach node execution failed: {e!s}",
            )
