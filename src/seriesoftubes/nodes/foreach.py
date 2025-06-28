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

            # Return ForEach configuration for the execution engine to handle
            # Similar to Split nodes, the engine will handle the actual subgraph execution
            return NodeResult(
                output={
                    "foreach_items": array_data,
                    "item_name": config.item_name,
                    "subgraph_nodes": config.subgraph_nodes,
                    "parallel": config.parallel,
                    "collect_output": config.collect_output,
                    "foreach_data": True,  # Flag to indicate this is foreach data
                },
                success=True,
                metadata={
                    "node_type": "foreach",
                    "iterations": len(array_data),
                    "subgraph_size": len(config.subgraph_nodes),
                    "parallel_execution": config.parallel,
                },
            )

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=f"ForEach node execution failed: {e!s}",
            )
