"""Split node executor for parallel processing of arrays"""

from typing import Any

from seriesoftubes.models import Node, SplitNodeConfig
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult


class SplitNodeExecutor(NodeExecutor):
    """Executor for split nodes that divide arrays into parallel processing streams"""

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute split node to create parallel processing streams
        
        Args:
            node: The split node to execute
            context: Execution context
            
        Returns:
            NodeResult with split items marked for parallel processing
        """
        try:
            config = node.config
            if not isinstance(config, SplitNodeConfig):
                return NodeResult(
                    output=None,
                    success=False,
                    error="Invalid config type for split node",
                )

            # Get context data for template rendering
            template_data = self.prepare_context_data(node, context)
            
            # Get the array data to split
            # Handle different field reference formats
            if config.field.startswith('inputs.'):
                # Direct input reference like "inputs.companies"
                input_name = config.field[7:]  # Remove "inputs." prefix
                if input_name in template_data.get('inputs', {}):
                    array_data = template_data['inputs'][input_name]
                else:
                    return NodeResult(
                        output=None,
                        success=False,
                        error=f"Input '{input_name}' not found",
                    )
            elif '.' in config.field:
                # Node output reference like "node_name.field_name"
                field_parts = config.field.split('.', 1)
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
            elif config.field in template_data:
                # Direct field reference
                array_data = template_data[config.field]
            else:
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Field '{config.field}' not found in context",
                )

            # Validate that we got an array
            if not isinstance(array_data, list):
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Field '{config.field}' is not an array (got {type(array_data).__name__})",
                )

            # Return the split configuration for the execution engine to handle
            # The engine will need to spawn parallel execution contexts
            return NodeResult(
                output={
                    "split_items": array_data,
                    "item_name": config.item_name,
                    "total_items": len(array_data),
                },
                success=True,
                metadata={
                    "node_type": "split",
                    "parallel_execution": True,
                    "split_count": len(array_data),
                }
            )

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=f"Split node execution failed: {str(e)}",
            )