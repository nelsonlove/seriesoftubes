"""Join node executor for combining multiple data sources"""

from typing import Any

from seriesoftubes.models import JoinNodeConfig, Node
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import JoinNodeInput, JoinNodeOutput


class JoinNodeExecutor(NodeExecutor):
    """Executor for join nodes that combine multiple data sources"""

    input_schema_class = JoinNodeInput
    output_schema_class = JoinNodeOutput

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute join node to combine data from multiple sources

        Args:
            node: The join node to execute
            context: Execution context

        Returns:
            NodeResult with joined data
        """
        try:
            config = node.config
            if not isinstance(config, JoinNodeConfig):
                return NodeResult(
                    output=None,
                    success=False,
                    error="Invalid config type for join node",
                )

            # Get context data for template rendering
            template_data = self.prepare_context_data(node, context)

            # Collect data from all sources
            source_data = {}
            for source_name, source_ref in config.sources.items():
                if source_ref.startswith("inputs."):
                    # Reference to workflow input
                    input_name = source_ref[7:]  # Remove "inputs." prefix
                    if input_name in template_data.get("inputs", {}):
                        source_data[source_name] = template_data["inputs"][input_name]
                    else:
                        return NodeResult(
                            output=None,
                            success=False,
                            error=f"Input '{input_name}' not found for source '{source_name}'",
                        )
                elif "." in source_ref:
                    # Reference to node output field
                    node_name, field_name = source_ref.split(".", 1)
                    node_output = context.get_output(node_name)
                    if isinstance(node_output, dict) and field_name in node_output:
                        source_data[source_name] = node_output[field_name]
                    else:
                        return NodeResult(
                            output=None,
                            success=False,
                            error=f"Field '{field_name}' not found in output of node '{node_name}' for source '{source_name}'",
                        )
                else:
                    # Reference to entire node output
                    node_output = context.get_output(source_ref)
                    if node_output is not None:
                        source_data[source_name] = node_output
                    else:
                        return NodeResult(
                            output=None,
                            success=False,
                            error=f"Output from node '{source_ref}' not found for source '{source_name}'",
                        )

            # Handle different join types
            result: Any
            if config.join_type == "inner":
                result = self._inner_join(source_data, config)
            elif config.join_type == "left":
                result = self._left_join(source_data, config)
            elif config.join_type == "right":
                result = self._right_join(source_data, config)
            elif config.join_type == "outer":
                result = self._outer_join(source_data, config)
            elif config.join_type == "cross":
                result = self._cross_join(source_data, config)
            elif config.join_type == "merge":
                result = self._merge_join(source_data, config)
            else:
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Unsupported join type: {config.join_type}",
                )

            return NodeResult(
                output=result,
                success=True,
                metadata={
                    "node_type": "join",
                    "join_type": config.join_type,
                    "sources": list(config.sources.keys()),
                    "result_count": len(result) if isinstance(result, list) else 1,
                },
            )

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=f"Join node execution failed: {e!s}",
            )

    def _inner_join(
        self, source_data: dict[str, Any], config: JoinNodeConfig
    ) -> list[dict[str, Any]]:
        """Perform inner join on arrays based on join keys"""
        if not config.join_keys:
            msg = "Inner join requires join_keys to be specified"
            raise ValueError(msg)

        # Get the first source as base
        source_names = list(source_data.keys())
        if len(source_names) < 2:
            msg = "Inner join requires at least 2 sources"
            raise ValueError(msg)

        base_source = source_names[0]
        base_data = source_data[base_source]

        if not isinstance(base_data, list):
            msg = f"Source '{base_source}' must be an array for inner join"
            raise ValueError(msg)

        results = []

        for base_item in base_data:
            # Start with base item
            joined_item = {base_source: base_item.copy()}

            # Try to join with other sources
            join_successful = True

            for other_source in source_names[1:]:
                other_data = source_data[other_source]
                if not isinstance(other_data, list):
                    msg = f"Source '{other_source}' must be an array for inner join"
                    raise ValueError(msg)

                # Find matching item
                matching_item = None
                for other_item in other_data:
                    if self._items_match(base_item, other_item, config.join_keys):
                        matching_item = other_item
                        break

                if matching_item:
                    # Add matching item as nested object
                    joined_item[other_source] = matching_item.copy()
                else:
                    # No match found - skip this base item
                    join_successful = False
                    break

            if join_successful:
                results.append(joined_item)

        return results

    def _left_join(
        self, source_data: dict[str, Any], config: JoinNodeConfig
    ) -> list[dict[str, Any]]:
        """Perform left join on arrays"""
        if not config.join_keys:
            msg = "Left join requires join_keys to be specified"
            raise ValueError(msg)

        source_names = list(source_data.keys())
        if len(source_names) < 2:
            msg = "Left join requires at least 2 sources"
            raise ValueError(msg)

        base_source = source_names[0]
        base_data = source_data[base_source]

        if not isinstance(base_data, list):
            msg = f"Source '{base_source}' must be an array for left join"
            raise ValueError(msg)

        results = []

        for base_item in base_data:
            # Start with base item
            joined_item = {base_source: base_item.copy()}

            # Try to join with other sources
            for other_source in source_names[1:]:
                other_data = source_data[other_source]
                if not isinstance(other_data, list):
                    msg = f"Source '{other_source}' must be an array for left join"
                    raise ValueError(msg)

                # Find matching item
                matching_item = None
                for other_item in other_data:
                    if self._items_match(base_item, other_item, config.join_keys):
                        matching_item = other_item
                        break

                if matching_item:
                    # Add matching item as nested object
                    joined_item[other_source] = matching_item.copy()
                else:
                    # No match - add None for the entire source
                    joined_item[other_source] = None

            results.append(joined_item)

        return results

    def _right_join(
        self, source_data: dict[str, Any], config: JoinNodeConfig
    ) -> list[dict[str, Any]]:
        """Perform right join on arrays"""
        if not config.join_keys:
            msg = "Right join requires join_keys to be specified"
            raise ValueError(msg)

        source_names = list(source_data.keys())
        if len(source_names) < 2:
            msg = "Right join requires at least 2 sources"
            raise ValueError(msg)

        # For right join, we use the second source as the base (right side)
        right_source = source_names[1]
        left_source = source_names[0]
        right_data = source_data[right_source]
        left_data = source_data[left_source]

        if not isinstance(right_data, list) or not isinstance(left_data, list):
            msg = "Sources must be arrays for right join"
            raise ValueError(msg)

        results = []

        for right_item in right_data:
            # Start with right item (preserve source order: left, right)
            joined_item = {right_source: right_item.copy()}

            # Find matching item in left source
            matching_item = None
            for left_item in left_data:
                if self._items_match(left_item, right_item, config.join_keys):
                    matching_item = left_item
                    break

            if matching_item:
                # Add matching left item
                joined_item[left_source] = matching_item.copy()
            else:
                # No match - add None for left source
                joined_item[left_source] = None

            results.append(joined_item)

        return results

    def _outer_join(
        self, source_data: dict[str, Any], config: JoinNodeConfig
    ) -> list[dict[str, Any]]:
        """Perform full outer join on arrays"""
        if not config.join_keys:
            msg = "Outer join requires join_keys to be specified"
            raise ValueError(msg)

        source_names = list(source_data.keys())
        if len(source_names) < 2:
            msg = "Outer join requires at least 2 sources"
            raise ValueError(msg)

        left_source = source_names[0]
        right_source = source_names[1]
        left_data = source_data[left_source]
        right_data = source_data[right_source]

        if not isinstance(left_data, list) or not isinstance(right_data, list):
            msg = "Sources must be arrays for outer join"
            raise ValueError(msg)

        results = []
        matched_right_indices = set()

        # Process left side (like left join)
        for left_item in left_data:
            joined_item = {left_source: left_item.copy()}

            # Find matching item in right source
            matching_item = None
            matching_index = None
            for i, right_item in enumerate(right_data):
                if self._items_match(left_item, right_item, config.join_keys):
                    matching_item = right_item
                    matching_index = i
                    break

            if matching_item:
                # Add matching right item
                joined_item[right_source] = matching_item.copy()
                matched_right_indices.add(matching_index)
            else:
                # No match - add None for right side
                joined_item[right_source] = None

            results.append(joined_item)

        # Add unmatched right items
        for i, right_item in enumerate(right_data):
            if i not in matched_right_indices:
                joined_item = {
                    left_source: None,
                    right_source: right_item.copy()
                }
                results.append(joined_item)

        return results

    def _cross_join(
        self, source_data: dict[str, Any], _config: JoinNodeConfig
    ) -> list[dict[str, Any]]:
        """Perform cross join (cartesian product) on arrays"""
        source_names = list(source_data.keys())
        if len(source_names) < 2:
            msg = "Cross join requires at least 2 sources"
            raise ValueError(msg)

        # Start with first source
        results = []
        base_source = source_names[0]
        base_data = source_data[base_source]

        if not isinstance(base_data, list):
            msg = f"Source '{base_source}' must be an array for cross join"
            raise ValueError(msg)

        # Initialize with base items
        for base_item in base_data:
            results.append({base_source: base_item.copy()})

        # Cross join with each additional source
        for other_source in source_names[1:]:
            other_data = source_data[other_source]
            if not isinstance(other_data, list):
                msg = f"Source '{other_source}' must be an array for cross join"
                raise ValueError(msg)

            new_results = []
            for result_item in results:
                for other_item in other_data:
                    # Combine result item with other item
                    combined_item = result_item.copy()
                    combined_item[other_source] = other_item.copy()
                    new_results.append(combined_item)

            results = new_results

        return results

    def _merge_join(
        self, source_data: dict[str, Any], config: JoinNodeConfig
    ) -> list[dict[str, Any]]:
        """Perform merge join (combines matching records by merging their fields)"""
        if not config.join_keys:
            msg = "Merge join requires join_keys to be specified"
            raise ValueError(msg)

        source_names = list(source_data.keys())
        if len(source_names) < 2:
            msg = "Merge join requires at least 2 sources"
            raise ValueError(msg)

        base_source = source_names[0]
        base_data = source_data[base_source]

        if not isinstance(base_data, list):
            msg = f"Source '{base_source}' must be an array for merge join"
            raise ValueError(msg)

        results = []

        for base_item in base_data:
            # Start with base item
            merged_item = base_item.copy()

            # Try to merge with other sources
            for other_source in source_names[1:]:
                other_data = source_data[other_source]
                if not isinstance(other_data, list):
                    msg = f"Source '{other_source}' must be an array for merge join"
                    raise ValueError(msg)

                # Find matching item
                for other_item in other_data:
                    if self._items_match(base_item, other_item, config.join_keys):
                        # Merge fields from matching item (overwriting if same key exists)
                        merged_item.update(other_item)
                        break

            results.append(merged_item)

        return results

    def _items_match(
        self, item1: dict[str, Any], item2: dict[str, Any], join_keys: dict[str, str]
    ) -> bool:
        """Check if two items match based on join keys"""
        for key1, key2 in join_keys.items():
            if item1.get(key1) != item2.get(key2):
                return False
        return True
