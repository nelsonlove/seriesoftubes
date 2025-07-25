"""Aggregate node executor for collecting parallel processing results"""

from typing import Any

from seriesoftubes.models import AggregateNodeConfig, Node
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import AggregateNodeInput, AggregateNodeOutput


class AggregateNodeExecutor(NodeExecutor):
    """Executor for aggregate nodes that collect results from parallel processing"""

    input_schema_class = AggregateNodeInput
    output_schema_class = AggregateNodeOutput

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute aggregate node to collect parallel processing results

        Args:
            node: The aggregate node to execute
            context: Execution context with parallel results

        Returns:
            NodeResult with aggregated data
        """
        try:
            config = node.config
            if not isinstance(config, AggregateNodeConfig):
                return NodeResult(
                    output=None,
                    success=False,
                    error="Invalid config type for aggregate node",
                )

            # Get the parallel results from context
            # The execution engine should have populated these
            parallel_results = []

            # Check if we have parallel execution results
            if hasattr(context, "parallel_results") and context.parallel_results:
                parallel_results = context.parallel_results
            else:
                # Look for results from dependent nodes that were split
                for dep_node in node.depends_on:
                    dep_output = context.get_output(dep_node)
                    
                    # Skip split metadata (dict with parallel_data flag)
                    if isinstance(dep_output, dict) and dep_output.get("parallel_data"):
                        # This is split metadata, extract the actual split items
                        split_items = dep_output.get("split_items", [])
                        if split_items:
                            parallel_results = split_items
                        else:
                            # Empty split - no items to aggregate
                            parallel_results = []
                        break
                    elif isinstance(dep_output, list):
                        # This is the output from a parallel processing node (like filter)
                        parallel_results = dep_output
                        break  # Take the first list output as our parallel results
                    elif dep_output is not None:
                        parallel_results.append(dep_output)

            # Apply field extraction if specified
            if config.field:
                extracted_results = []
                for result in parallel_results:
                    if isinstance(result, dict) and config.field in result:
                        extracted_results.append(result[config.field])
                    else:
                        # If field doesn't exist, include None or skip
                        extracted_results.append(None)
                parallel_results = extracted_results

            # Aggregate based on mode
            aggregated_output: Any
            if config.mode == "array":
                # Simple array of results
                aggregated_output = parallel_results

            elif config.mode == "object":
                # Convert to object with indices as keys
                aggregated_output = {
                    str(i): result for i, result in enumerate(parallel_results)
                }

            elif config.mode == "merge":
                # Merge all dict results into single dict
                aggregated_output = {}
                for i, result in enumerate(parallel_results):
                    if isinstance(result, dict):
                        # Add index prefix to avoid key conflicts
                        for key, value in result.items():
                            aggregated_output[f"{i}_{key}"] = value
                    else:
                        aggregated_output[f"result_{i}"] = result
            else:
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Unknown aggregation mode: {config.mode}",
                )

            return NodeResult(
                output=aggregated_output,
                success=True,
                metadata={
                    "node_type": "aggregate",
                    "aggregation_mode": config.mode,
                    "item_count": len(parallel_results),
                },
            )

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=f"Aggregate node execution failed: {e!s}",
            )
