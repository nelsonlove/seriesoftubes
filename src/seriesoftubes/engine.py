"""DAG execution engine for seriesoftubes workflows"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from seriesoftubes.cache import get_cache_backend
from seriesoftubes.cache.manager import CACHE_SETTINGS, CacheManager
from seriesoftubes.config import get_config
from seriesoftubes.models import Node, NodeType, Workflow
from seriesoftubes.nodes import (
    AggregateNodeExecutor,
    ConditionalNodeExecutor,
    FileNodeExecutor,
    FilterNodeExecutor,
    ForEachNodeExecutor,
    HTTPNodeExecutor,
    JoinNodeExecutor,
    LLMNodeExecutor,
    NodeExecutor,
    NodeResult,
    PythonNodeExecutor,
    SplitNodeExecutor,
    TransformNodeExecutor,
)
from seriesoftubes.storage import StorageError, get_storage_backend


class ExecutionContext:
    """Context for workflow execution"""

    def __init__(self, workflow: Workflow, inputs: dict[str, Any]):
        self.workflow = workflow
        self.inputs = inputs
        self.outputs: dict[str, Any] = {}
        self.errors: dict[str, str] = {}
        self.execution_id = str(uuid4())
        self.start_time = datetime.now(timezone.utc)
        self.validation_errors: dict[str, list[str]] = {}  # Node validation errors
        self.storage_keys: dict[str, str] = {}  # Storage keys for outputs

        # Parallel execution support
        self.parallel_results: list[Any] = []  # Results from parallel processing
        self.split_contexts: dict[str, list[ExecutionContext]] = (
            {}
        )  # Split node contexts
        self.is_parallel_context = False  # Whether this is a parallel execution context
        self.parent_context: ExecutionContext | None = (
            None  # Parent context for parallel execution
        )

    def get_output(self, node_name: str) -> Any:
        """Get output from a previous node"""
        return self.outputs.get(node_name)

    def get_input(self, input_name: str) -> Any:
        """Get workflow input value"""
        return self.inputs.get(input_name)

    def set_output(self, node_name: str, output: Any) -> None:
        """Store output from a node"""
        self.outputs[node_name] = output

    def set_error(self, node_name: str, error: str) -> None:
        """Store error from a node"""
        self.errors[node_name] = error

    def add_validation_error(self, node_name: str, error: str) -> None:
        """Add a validation error for a node"""
        if node_name not in self.validation_errors:
            self.validation_errors[node_name] = []
        self.validation_errors[node_name].append(error)


class WorkflowEngine:
    """Engine for executing workflows"""

    def __init__(self, cache_manager: CacheManager | None = None) -> None:
        # Map node types to their executors
        self.executors: dict[NodeType, NodeExecutor] = {
            NodeType.LLM: LLMNodeExecutor(),
            NodeType.HTTP: HTTPNodeExecutor(),
            NodeType.FILE: FileNodeExecutor(),
            NodeType.PYTHON: PythonNodeExecutor(),
            NodeType.SPLIT: SplitNodeExecutor(),
            NodeType.AGGREGATE: AggregateNodeExecutor(),
            NodeType.FILTER: FilterNodeExecutor(),
            NodeType.TRANSFORM: TransformNodeExecutor(),
            NodeType.JOIN: JoinNodeExecutor(),
            NodeType.FOREACH: ForEachNodeExecutor(),
            NodeType.CONDITIONAL: ConditionalNodeExecutor(),
        }

        # Initialize cache manager
        if cache_manager is None:
            try:
                config = get_config()
                if config.cache.enabled:
                    backend = get_cache_backend(
                        backend_type=config.cache.backend,
                        redis_url=config.cache.redis_url,
                        db=config.cache.redis_db,
                        key_prefix=config.cache.key_prefix,
                    )
                    self.cache_manager = CacheManager(backend, config.cache.default_ttl)
                else:
                    self.cache_manager = None
            except Exception as e:
                logging.warning(f"Failed to initialize cache: {e}")
                self.cache_manager = None
        else:
            self.cache_manager = cache_manager

    async def execute(
        self, workflow: Workflow, inputs: dict[str, Any] | None = None
    ) -> ExecutionContext:
        """Execute a workflow

        Args:
            workflow: The workflow to execute
            inputs: Input values for the workflow

        Returns:
            ExecutionContext with results
        """
        # Validate and prepare inputs
        validated_inputs = self._validate_inputs(workflow, inputs or {})

        # Create execution context
        context = ExecutionContext(workflow, validated_inputs)

        # Get execution order and groups for parallel execution
        try:
            execution_groups = self._get_execution_groups(workflow)
        except ValueError:
            # If there's a dependency error, create a simplified execution plan
            # that will attempt to execute each node and fail at the node level
            execution_groups = [[node_name] for node_name in workflow.nodes.keys()]

        # Track split contexts for parallel execution
        split_data: dict[str, dict[str, Any]] = {}  # node_name -> split info
        
        # Track foreach contexts for subgraph execution
        foreach_data: dict[str, dict[str, Any]] = {}  # node_name -> foreach info

        # Execute nodes in parallel groups
        for group in execution_groups:
            # Skip if we've encountered errors (fail fast)
            if context.errors:
                break

            # Check if any node in this group follows a split node
            group_has_split_dependency = False
            split_source = None

            for node_name in group:
                node = workflow.nodes[node_name]
                for dep in node.depends_on:
                    if dep in split_data:
                        group_has_split_dependency = True
                        split_source = dep
                        break
                if group_has_split_dependency:
                    break

            if group_has_split_dependency and split_source:
                # Execute this group in parallel for each split item
                await self._execute_split_group(
                    group, context, split_data[split_source]
                )
            else:
                # Regular parallel execution within group
                tasks = []
                for node_name in group:
                    node = workflow.nodes[node_name]

                    # Check if we should skip this node
                    if self._should_skip_node(node, context):
                        continue
                    
                    # Check for missing dependencies
                    missing_deps = [dep for dep in node.depends_on if dep not in workflow.nodes]
                    if missing_deps:
                        context.set_error(node_name, f"Missing dependencies: {', '.join(missing_deps)}")
                        continue

                    # Check if this is a split node
                    if node.node_type == NodeType.SPLIT:
                        result = await self._execute_split_node(
                            node_name, node, context
                        )
                        if result.success and isinstance(result.output, dict):
                            split_data[node_name] = result.output
                            context.set_output(node_name, result.output)
                        else:
                            context.set_error(
                                node_name, result.error or "Split node failed"
                            )
                    elif node.node_type == NodeType.FOREACH:
                        # ForEach nodes execute subgraphs immediately
                        result = await self._execute_foreach_node(
                            node_name, node, context
                        )
                        if result.success:
                            context.set_output(node_name, result.output)
                        else:
                            context.set_error(
                                node_name, result.error or "ForEach node failed"
                            )
                    else:
                        # Create task for this node
                        tasks.append(self._execute_node_async(node_name, node, context))

                # Wait for all tasks in this group to complete
                if tasks:
                    await asyncio.gather(*tasks)

        return context

    def _validate_inputs(
        self, workflow: Workflow, provided_inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate and prepare workflow inputs"""
        validated = {}

        for input_name, input_def in workflow.inputs.items():
            if input_name in provided_inputs:
                # TODO: Add type validation based on input_def.input_type
                validated[input_name] = provided_inputs[input_name]
            elif input_def.required:
                msg = f"Required input '{input_name}' not provided"
                raise ValueError(msg)
            elif input_def.default is not None:
                validated[input_name] = input_def.default

        # Warn about extra inputs
        extra_inputs = set(provided_inputs.keys()) - set(workflow.inputs.keys())
        if extra_inputs:
            # For now, just ignore extra inputs
            pass

        return validated

    def _should_skip_node(self, node: Node, context: ExecutionContext) -> bool:
        """Check if a node should be skipped

        This is used for routing and to skip nodes that are part of ForEach subgraphs.
        """
        # Skip nodes that are part of ForEach subgraphs during main execution
        for workflow_node in context.workflow.nodes.values():
            if workflow_node.node_type == NodeType.FOREACH:
                from seriesoftubes.models import ForEachNodeConfig
                if isinstance(workflow_node.config, ForEachNodeConfig):
                    if node.name in workflow_node.config.subgraph_nodes:
                        return True
        
        return False

    async def _execute_node(self, node: Node, context: ExecutionContext) -> NodeResult:
        """Execute a single node with caching support"""
        # Get the appropriate executor
        executor = self.executors.get(node.node_type)
        if not executor:
            return NodeResult(
                output=None,
                success=False,
                error=f"No executor for node type: {node.node_type}",
            )

        # Check cache if available
        if self.cache_manager is not None:
            node_type = (
                node.node_type.value
                if hasattr(node.node_type, "value")
                else str(node.node_type)
            )
            cache_settings = CACHE_SETTINGS.get(node_type, {})

            if cache_settings.get("enabled", False):
                # Prepare context data for caching
                context_data = {
                    "inputs": context.inputs,
                    "outputs": dict(context.outputs.items()),
                }

                # Get exclude keys from cache settings
                exclude_keys = cache_settings.get("exclude_context_keys", [])

                try:
                    # Try to get cached result
                    cached_result = await self.cache_manager.get_cached_result(
                        node_type=node_type,
                        node_name=node.name,
                        config=node.config,
                        context_data=context_data,
                        exclude_context_keys=exclude_keys,
                    )

                    if cached_result is not None:
                        # Return cached result
                        result = NodeResult(
                            output=cached_result,
                            success=True,
                            metadata={"cache_hit": True},
                        )

                        # Still validate cached output
                        if result.success:
                            validation_errors = self._validate_node_output(
                                node, result.output, context
                            )
                            if validation_errors:
                                for error in validation_errors:
                                    context.add_validation_error(node.name, error)

                        return result
                except Exception as e:
                    # Cache read error - continue with normal execution
                    logging.warning(f"Cache read error for node {node.name}: {e}")

        # Execute the node normally
        result = await executor.execute(node, context)

        # Cache successful results
        if (
            self.cache_manager is not None
            and result.success
            and result.output is not None
        ):
            node_type = (
                node.node_type.value
                if hasattr(node.node_type, "value")
                else str(node.node_type)
            )
            cache_settings = CACHE_SETTINGS.get(node_type, {})

            if cache_settings.get("enabled", False):
                try:
                    # Prepare context data for caching
                    context_data = {
                        "inputs": context.inputs,
                        "outputs": dict(context.outputs.items()),
                    }

                    exclude_keys = cache_settings.get("exclude_context_keys", [])
                    cache_ttl = cache_settings.get("ttl")

                    await self.cache_manager.cache_result(
                        node_type=node_type,
                        node_name=node.name,
                        config=node.config,
                        context_data=context_data,
                        result=result.output,
                        ttl=cache_ttl,
                        exclude_context_keys=exclude_keys,
                    )

                    # Add cache metadata
                    if result.metadata is None:
                        result.metadata = {}
                    result.metadata["cache_hit"] = False

                except Exception as e:
                    # Cache write error - don't fail the execution
                    logging.warning(f"Cache write error for node {node.name}: {e}")

        # If execution was successful, validate output against downstream requirements
        if result.success:
            validation_errors = self._validate_node_output(node, result.output, context)
            if validation_errors:
                for error in validation_errors:
                    context.add_validation_error(node.name, error)
                # Note: We don't fail the node here, just record validation errors
                # This allows the workflow to continue and collect all validation issues

        return result

    async def _execute_node_async(
        self, node_name: str, node: Node, context: ExecutionContext
    ) -> None:
        """Execute a node and update context (for parallel execution)"""
        try:
            # Special handling for split nodes
            if node.node_type == NodeType.SPLIT:
                result = await self._execute_split_node(node_name, node, context)
            else:
                result = await self._execute_node(node, context)

            if result.success:
                context.set_output(node_name, result.output)
            else:
                context.set_error(node_name, result.error or "Unknown error")
        except Exception as e:
            context.set_error(node_name, str(e))

    async def _execute_split_node(
        self, _node_name: str, node: Node, context: ExecutionContext
    ) -> NodeResult:
        """Execute a split node and set up parallel execution contexts"""
        # Execute the split node normally first
        result = await self._execute_node(node, context)

        if not result.success:
            return result

        # Extract split information
        split_output = result.output
        if not isinstance(split_output, dict) or "split_items" not in split_output:
            return NodeResult(
                output=None,
                success=False,
                error="Split node did not return expected split_items format",
            )

        split_items = split_output["split_items"]
        item_name = split_output.get("item_name", "item")

        # Return split information for the execution engine to handle
        return NodeResult(
            output={
                "split_items": split_items,
                "item_name": item_name,
                "parallel_data": True,  # Flag to indicate this is parallel data
            },
            success=True,
            metadata=result.metadata,
        )

    async def _execute_foreach_node(
        self, node_name: str, node: Node, context: ExecutionContext
    ) -> NodeResult:
        """Execute a foreach node and its subgraphs"""
        # First execute the foreach node to get the iteration data
        result = await self._execute_node(node, context)

        if not result.success:
            return result

        # Extract foreach information
        foreach_output = result.output
        if not isinstance(foreach_output, dict) or "foreach_items" not in foreach_output:
            return NodeResult(
                output=None,
                success=False,
                error="ForEach node did not return expected foreach_items format",
            )

        foreach_items = foreach_output["foreach_items"]
        item_name = foreach_output.get("item_name", "item")
        subgraph_nodes = foreach_output.get("subgraph_nodes", [])
        parallel = foreach_output.get("parallel", True)
        collect_output = foreach_output.get("collect_output")

        # Execute subgraph for each item
        if parallel:
            results = await self._execute_foreach_parallel(
                foreach_items, item_name, subgraph_nodes, context, collect_output
            )
        else:
            results = await self._execute_foreach_sequential(
                foreach_items, item_name, subgraph_nodes, context, collect_output
            )

        return NodeResult(
            output=results,
            success=True,
            metadata={
                "node_type": "foreach",
                "iterations": len(foreach_items),
                "subgraph_size": len(subgraph_nodes),
                "parallel_execution": parallel,
            },
        )

    async def _execute_split_group(
        self, group: list[str], context: ExecutionContext, split_info: dict[str, Any]
    ) -> None:
        """Execute a group of nodes in parallel for each split item"""
        split_items = split_info["split_items"]
        item_name = split_info["item_name"]

        # Create parallel execution tasks for each split item
        parallel_tasks = []

        for item_index, item in enumerate(split_items):
            # Create a parallel execution context for this item
            parallel_context = ExecutionContext(context.workflow, context.inputs)
            parallel_context.is_parallel_context = True
            parallel_context.parent_context = context

            # Copy existing outputs to parallel context
            parallel_context.outputs = context.outputs.copy()

            # Add the current item to the parallel context
            # Add it both as an output and as a special attribute for context preparation
            parallel_context.outputs[item_name] = item
            # Store the item in a way that prepare_context_data can access it
            setattr(parallel_context, f"_split_item_{item_name}", item)

            # Create task to execute this group for this item
            task = self._execute_group_for_item(group, parallel_context, item_index)
            parallel_tasks.append(task)

        # Execute all parallel tasks
        parallel_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)

        # Collect results and handle aggregate nodes
        for node_name in group:
            node = context.workflow.nodes[node_name]

            if node.node_type == NodeType.AGGREGATE:
                # Aggregate the parallel results
                item_results = []
                for i, result in enumerate(parallel_results):
                    if isinstance(result, Exception):
                        context.set_error(f"{node_name}_item_{i}", str(result))
                    elif isinstance(result, dict) and node_name in result:
                        item_results.append(result[node_name])

                # Execute the aggregate node with collected results
                aggregate_context = ExecutionContext(context.workflow, context.inputs)
                aggregate_context.outputs = context.outputs.copy()
                aggregate_context.parallel_results = item_results

                aggregate_result = await self._execute_node(node, aggregate_context)
                if aggregate_result.success:
                    context.set_output(node_name, aggregate_result.output)
                else:
                    context.set_error(
                        node_name, aggregate_result.error or "Aggregate failed"
                    )
            else:
                # For non-aggregate nodes, collect all results as array
                item_results = []
                for i, result in enumerate(parallel_results):
                    if isinstance(result, Exception):
                        context.set_error(f"{node_name}_item_{i}", str(result))
                    elif isinstance(result, dict) and node_name in result:
                        item_results.append(result[node_name])

                context.set_output(node_name, item_results)

    async def _execute_group_for_item(
        self, group: list[str], parallel_context: ExecutionContext, _item_index: int
    ) -> dict[str, Any]:
        """Execute a group of nodes for a single split item"""
        results = {}

        for node_name in group:
            node = parallel_context.workflow.nodes[node_name]

            # Skip aggregate nodes in parallel execution - they'll be handled later
            if node.node_type == NodeType.AGGREGATE:
                continue

            try:
                result = await self._execute_node(node, parallel_context)
                if result.success:
                    parallel_context.set_output(node_name, result.output)
                    results[node_name] = result.output
                else:
                    parallel_context.set_error(
                        node_name, result.error or "Unknown error"
                    )
                    results[node_name] = None
            except Exception as e:
                parallel_context.set_error(node_name, str(e))
                results[node_name] = None

        return results

    def _get_execution_groups(self, workflow: Workflow) -> list[list[str]]:
        """Group nodes by execution level for parallel processing

        Returns list of groups where each group contains nodes that can run in parallel
        """
        nodes = workflow.nodes
        levels: dict[str, int] = {}  # Node name -> execution level

        # Calculate execution level for each node
        def get_level(node_name: str) -> int:
            if node_name in levels:
                return levels[node_name]

            if node_name not in nodes:
                msg = f"Node '{node_name}' referenced in dependencies but not found in workflow"
                raise ValueError(msg)

            node = nodes[node_name]
            if not node.depends_on:
                levels[node_name] = 0
            else:
                # Level is max of dependencies + 1
                dep_levels = [get_level(dep) for dep in node.depends_on]
                levels[node_name] = max(dep_levels) + 1

            return levels[node_name]

        # Calculate levels for all nodes
        for node_name in nodes:
            get_level(node_name)

        # Group nodes by level
        max_level = max(levels.values()) if levels else -1
        groups = []
        for level in range(max_level + 1):
            group = [name for name, node_level in levels.items() if node_level == level]
            if group:
                groups.append(group)

        return groups

    def _validate_node_output(
        self, node: Node, output: Any, context: ExecutionContext
    ) -> list[str]:
        """Validate node output against downstream node requirements

        Returns list of validation error messages
        """
        errors = []

        # Find all nodes that depend on this one
        downstream_nodes = [
            n for n in context.workflow.nodes.values() if node.name in n.depends_on
        ]

        for downstream_node in downstream_nodes:
            # Get the executor for the downstream node to check its input schema
            downstream_executor = self.executors.get(downstream_node.node_type)
            if not downstream_executor or not downstream_executor.input_schema_class:
                continue

            # Check if the downstream node expects this node's output
            if downstream_node.config and hasattr(downstream_node.config, "context"):
                context_mapping = downstream_node.config.context
                if context_mapping is None:
                    continue

                # Find which context keys map to this node's output
                for context_key, source in context_mapping.items():
                    if source == node.name:
                        # For now, just check basic type compatibility
                        # Full schema validation would require understanding how
                        # the output maps to the downstream node's full input
                        # This is a simplified check
                        if output is None:
                            errors.append(
                                f"Output is None but required by "
                                f"{downstream_node.name}.{context_key}"
                            )

        return errors

    async def _execute_foreach_parallel(
        self,
        foreach_items: list[Any],
        item_name: str,
        subgraph_nodes: list[str],
        context: ExecutionContext,
        collect_output: str | None,
    ) -> list[Any]:
        """Execute foreach subgraph in parallel for each item"""
        # Create parallel execution tasks for each item
        parallel_tasks = []

        for item_index, item in enumerate(foreach_items):
            # Create task to execute subgraph for this item
            task = self._execute_subgraph_for_item(
                item, item_index, item_name, subgraph_nodes, context, collect_output
            )
            parallel_tasks.append(task)

        # Execute all parallel tasks
        parallel_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)

        # Collect successful results
        results = []
        for i, result in enumerate(parallel_results):
            if isinstance(result, Exception):
                # For now, include None for failed iterations
                # Could be configurable behavior (fail fast vs continue)
                results.append(None)
            else:
                results.append(result)

        return results

    async def _execute_foreach_sequential(
        self,
        foreach_items: list[Any],
        item_name: str,
        subgraph_nodes: list[str],
        context: ExecutionContext,
        collect_output: str | None,
    ) -> list[Any]:
        """Execute foreach subgraph sequentially for each item"""
        results = []

        for item_index, item in enumerate(foreach_items):
            try:
                result = await self._execute_subgraph_for_item(
                    item, item_index, item_name, subgraph_nodes, context, collect_output
                )
                results.append(result)
            except Exception:
                # For now, include None for failed iterations
                # Could be configurable behavior (fail fast vs continue)
                results.append(None)

        return results

    async def _execute_subgraph_for_item(
        self,
        item: Any,
        item_index: int,
        item_name: str,
        subgraph_nodes: list[str],
        parent_context: ExecutionContext,
        collect_output: str | None,
    ) -> Any:
        """Execute a subgraph for a single foreach item"""
        # Create isolated execution context for this iteration
        iteration_context = ExecutionContext(parent_context.workflow, parent_context.inputs)
        iteration_context.is_parallel_context = True  # Mark as parallel context for node detection
        iteration_context.parent_context = parent_context
        
        # Copy parent outputs (so subgraph can access nodes executed before foreach)
        iteration_context.outputs = parent_context.outputs.copy()
        
        # Add the current item to the context
        iteration_context.outputs[item_name] = item
        
        # Add iteration metadata
        iteration_context.outputs["_iteration_index"] = item_index
        iteration_context.outputs["_is_first"] = item_index == 0
        iteration_context.outputs["_is_last"] = item_index == len(parent_context.outputs) - 1

        # Execute subgraph nodes in dependency order
        subgraph_workflow = self._create_subgraph_workflow(
            parent_context.workflow, subgraph_nodes
        )
        subgraph_groups = self._get_execution_groups(subgraph_workflow)

        # Execute subgraph
        for group in subgraph_groups:
            # Only execute nodes that are in our subgraph
            filtered_group = [name for name in group if name in subgraph_nodes]
            if not filtered_group:
                continue

            tasks = []
            for node_name in filtered_group:
                node = parent_context.workflow.nodes[node_name]
                tasks.append(self._execute_node_async(node_name, node, iteration_context))

            if tasks:
                await asyncio.gather(*tasks)

        # Return the specified output or the result of the last node
        if collect_output and collect_output in iteration_context.outputs:
            result = iteration_context.outputs[collect_output]
        elif subgraph_nodes:
            # Return the output of the last node in the subgraph
            last_node = subgraph_nodes[-1]
            result = iteration_context.outputs.get(last_node)
        else:
            # Return the item itself if no subgraph
            result = item
        
        # Unwrap schema-wrapped results for final ForEach output
        # This only applies to the final result, not intermediate results in multi-node subgraphs
        if (isinstance(result, dict) and "result" in result and len(result) == 1 
            and isinstance(result["result"], (dict, list, str, int, float, bool, type(None)))):
            result = result["result"]
        
        return result

    def _create_subgraph_workflow(self, workflow: Workflow, subgraph_nodes: list[str]) -> Workflow:
        """Create a workflow containing only the specified subgraph nodes"""
        subgraph_workflow_nodes = {}
        
        for node_name in subgraph_nodes:
            if node_name in workflow.nodes:
                subgraph_workflow_nodes[node_name] = workflow.nodes[node_name]

        return Workflow(
            name=f"{workflow.name}_subgraph",
            version=workflow.version,
            inputs=workflow.inputs,
            nodes=subgraph_workflow_nodes,
            outputs={},  # Subgraph doesn't need outputs mapping
        )

    async def close(self) -> None:
        """Close the engine and cleanup resources"""
        if self.cache_manager is not None:
            await self.cache_manager.close()


async def save_outputs_to_storage(
    execution_id: str,
    workflow_name: str,
    outputs: dict[str, Any],
    user_id: Optional[str] = None,
    storage_prefix: Optional[str] = None,
) -> dict[str, str]:
    """Save execution outputs to object storage
    
    Args:
        execution_id: Unique execution ID
        workflow_name: Name of the workflow
        outputs: Dictionary of output name -> output data
        user_id: Optional user ID for scoping storage
        storage_prefix: Optional custom storage prefix
        
    Returns:
        Dictionary mapping output names to storage keys
    """
    storage_keys = {}
    
    try:
        storage = get_storage_backend()
        await storage.initialize()
        
        # Determine base prefix
        if storage_prefix:
            base_prefix = storage_prefix
        elif user_id:
            base_prefix = f"{user_id}/executions/{execution_id}"
        else:
            base_prefix = f"executions/{execution_id}"
        
        # Save execution metadata
        metadata = {
            "execution_id": execution_id,
            "workflow_name": workflow_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "output_count": len(outputs),
        }
        
        metadata_key = f"{base_prefix}/metadata.json"
        await storage.upload(
            key=metadata_key,
            content=json.dumps(metadata, indent=2).encode("utf-8"),
            content_type="application/json",
        )
        storage_keys["__metadata__"] = metadata_key
        
        # Save each output
        for output_name, output_data in outputs.items():
            # Determine format based on data type
            if isinstance(output_data, (dict, list)):
                content = json.dumps(output_data, indent=2).encode("utf-8")
                content_type = "application/json"
                extension = "json"
            else:
                content = str(output_data).encode("utf-8")
                content_type = "text/plain"
                extension = "txt"
            
            # Create storage key
            output_key = f"{base_prefix}/outputs/{output_name}.{extension}"
            
            # Upload to storage
            await storage.upload(
                key=output_key,
                content=content,
                content_type=content_type,
                metadata={
                    "execution_id": execution_id,
                    "workflow_name": workflow_name,
                    "output_name": output_name,
                }
            )
            
            storage_keys[output_name] = output_key
            
    except StorageError as e:
        logging.error(f"Failed to save outputs to storage: {e}")
        # Return partial results if some uploads succeeded
        
    return storage_keys


async def run_workflow(
    workflow: Workflow,
    inputs: dict[str, Any] | None = None,
    *,
    save_outputs: bool = True,
    output_dir: Path | None = None,
    save_to_storage: bool = False,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """High-level function to run a workflow

    Args:
        workflow: The workflow to execute
        inputs: Input values
        save_outputs: Whether to save outputs to disk
        output_dir: Base directory for outputs (defaults to ./outputs)
        save_to_storage: Whether to save outputs to object storage
        user_id: Optional user ID for storage scoping

    Returns:
        Dictionary with execution results
    """
    engine = WorkflowEngine()
    context = await engine.execute(workflow, inputs)

    # Prepare results
    results: dict[str, Any] = {
        "execution_id": context.execution_id,
        "start_time": context.start_time.isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "success": len(context.errors) == 0,
        "outputs": {},
        "errors": context.errors,
        "validation_errors": context.validation_errors,
    }

    # Map final outputs
    for output_name, node_name in workflow.outputs.items():
        if node_name in context.outputs:
            results["outputs"][output_name] = context.outputs[node_name]

    # Save outputs to object storage if requested
    if save_to_storage and results["outputs"]:
        storage_keys = await save_outputs_to_storage(
            execution_id=context.execution_id,
            workflow_name=workflow.name,
            outputs=results["outputs"],
            user_id=user_id,
        )
        results["storage_keys"] = storage_keys

    # Save outputs to disk if requested
    if save_outputs:
        base_dir = output_dir or Path("outputs")
        exec_output_dir = base_dir / context.execution_id
        exec_output_dir.mkdir(parents=True, exist_ok=True)

        # Save execution summary
        with open(exec_output_dir / "execution.json", "w") as f:
            json.dump(results, f, indent=2)

        # Save individual node outputs
        for node_name, output in context.outputs.items():
            with open(exec_output_dir / f"{node_name}.json", "w") as f:
                json.dump(output, f, indent=2)

    return results
