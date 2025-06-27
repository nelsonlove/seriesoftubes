# Test that transformations are deterministic and preserve structure
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from seriesoftubes.engine import WorkflowEngine
from seriesoftubes.models import (
    Node,
    NodeType,
    SplitNodeConfig,
    TransformNodeConfig,
    Workflow,
    WorkflowInput,
)
from tests.test_nodes.test_data_flow_hypothesis import companies_strategy

transform_template_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=st.one_of(
        st.just("{{ item.name }}"),
        st.just("{{ item.revenue }}"),
        st.just("{{ item.employees }}"),
        st.just("{{ item.name | upper }}"),
        st.just("{{ item.revenue / 1000 }}"),
    ),
    min_size=1,
    max_size=5,
)


@given(companies=companies_strategy, template=transform_template_strategy)
@pytest.mark.asyncio
async def test_transform_deterministic(companies, template):
    """Transform with same input/template should always produce same output"""
    assume(len(companies) > 0)

    engine = WorkflowEngine()

    async def run_transform():
        workflow = Workflow(
            name="test-transform",
            version="1.0.0",
            inputs={"companies": WorkflowInput(input_type="array", required=True)},
            nodes={
                "split": Node(
                    name="split",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(
                        field="inputs.companies", item_name="company"
                    ),
                ),
                "transform": Node(
                    name="transform",
                    type=NodeType.TRANSFORM,
                    depends_on=["split"],
                    config=TransformNodeConfig(template=template),
                ),
            },
        )

        context = await engine.execute(workflow, {"companies": companies})
        return context.outputs["transform"]

    # Run twice and verify same output
    result1 = await run_transform()
    result2 = await run_transform()

    assert result1 == result2
