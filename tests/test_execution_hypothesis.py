import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from seriesoftubes.engine import WorkflowEngine
from seriesoftubes.models import Node, NodeType, PythonNodeConfig, Workflow


@given(
    num_parallel_nodes=st.integers(min_value=2, max_value=4),
)
@settings(deadline=2000)  # 2 second deadline for process overhead
@pytest.mark.asyncio
async def test_parallel_execution_functionality(num_parallel_nodes):
    """Parallel execution should execute all independent nodes successfully"""
    
    # Create workflow with N independent nodes that each return their ID
    nodes = {}
    for i in range(num_parallel_nodes):
        nodes[f"node_{i}"] = Node(
            name=f"node_{i}",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(
                code=f"return {{'id': {i}, 'executed': True}}"
            ),
        )

    workflow = Workflow(name="parallel-test", version="1.0.0", nodes=nodes)
    engine = WorkflowEngine()
    
    context = await engine.execute(workflow, {})

    # All nodes should execute successfully
    assert len(context.errors) == 0
    assert len(context.outputs) == num_parallel_nodes
    
    # Each node should have returned its expected result
    for i in range(num_parallel_nodes):
        node_output = context.outputs[f"node_{i}"]
        assert node_output["result"]["id"] == i
        assert node_output["result"]["executed"] is True
