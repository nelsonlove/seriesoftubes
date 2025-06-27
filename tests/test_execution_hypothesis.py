import time

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from seriesoftubes.engine import WorkflowEngine
from seriesoftubes.models import Node, NodeType, PythonNodeConfig, Workflow


@given(
    num_parallel_nodes=st.integers(min_value=2, max_value=10),
    node_delays=st.lists(
        st.floats(min_value=0.01, max_value=0.1), min_size=2, max_size=10
    ),
)
@pytest.mark.asyncio
async def test_parallel_execution_faster_than_serial(num_parallel_nodes, node_delays):
    """Parallel execution should be faster than serial for independent nodes"""
    assume(len(node_delays) >= num_parallel_nodes)

    # Create workflow with N independent nodes
    nodes = {}
    for i in range(num_parallel_nodes):
        nodes[f"node_{i}"] = Node(
            name=f"node_{i}",
            type=NodeType.PYTHON,
            config=PythonNodeConfig(
                code=f"import time; time.sleep({node_delays[i]}); return {{'id': {i}}}"
            ),
        )

    workflow = Workflow(name="parallel-test", version="1.0.0", nodes=nodes)

    engine = WorkflowEngine()

    start = time.time()
    await engine.execute(workflow, {})
    parallel_time = time.time() - start

    # Parallel time should be close to max delay, not sum
    max_delay = max(node_delays[:num_parallel_nodes])
    sum_delays = sum(node_delays[:num_parallel_nodes])

    assert parallel_time < sum_delays * 0.8  # Allow some overhead
    assert parallel_time < max_delay * 2  # Should be close to max delay
