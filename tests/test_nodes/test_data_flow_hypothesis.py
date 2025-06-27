import hypothesis.strategies as st
import pytest
from hypothesis import assume, given, settings

from seriesoftubes.engine import WorkflowEngine
from seriesoftubes.models import (
    FilterNodeConfig,
    Node,
    NodeType,
    SplitNodeConfig,
    TransformNodeConfig,
    Workflow,
    WorkflowInput,
)

# Strategy for generating test data
company_strategy = st.fixed_dictionaries(
    {
        "id": st.integers(min_value=1),
        "name": st.text(min_size=1, max_size=50),
        "revenue": st.integers(min_value=0, max_value=10**9),
        "employees": st.integers(min_value=1, max_value=100000),
        "industry": st.sampled_from(["Tech", "Finance", "Healthcare", "Retail"]),
    }
)

companies_strategy = st.lists(company_strategy, min_size=0, max_size=100)


class TestDataFlowProperties:
    """Property-based tests for data flow nodes"""

    @given(companies=companies_strategy)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_split_filter_preserves_data(self, companies):
        """Split + Filter should never create or lose data fields"""
        engine = WorkflowEngine()

        workflow = Workflow(
            name="test-split-filter",
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
                "filter": Node(
                    name="filter",
                    type=NodeType.FILTER,
                    depends_on=["split"],
                    config=FilterNodeConfig(
                        condition="{{ company.revenue > 1000000 }}"
                    ),
                ),
            },
        )

        context = await engine.execute(workflow, {"companies": companies})

        # Properties to verify:
        # 1. Filter output length equals input length (with None for filtered items)
        filtered = context.outputs.get("filter", [])
        assert len(filtered) == len(companies)

        # 2. Non-None items maintain all original fields
        for original, filtered_item in zip(companies, filtered, strict=False):
            if filtered_item is not None:
                assert filtered_item == original
                assert original["revenue"] > 1000000

        # 3. All items with revenue > 1M are present
        high_revenue = [c for c in companies if c["revenue"] > 1000000]
        filtered_non_null = [f for f in filtered if f is not None]
        assert len(high_revenue) == len(filtered_non_null)

    @given(
        companies=companies_strategy,
        threshold=st.integers(min_value=0, max_value=10**9),
    )
    @pytest.mark.asyncio
    async def test_filter_threshold_consistency(self, companies, threshold):
        """Filter results should be consistent with threshold"""
        assume(len(companies) > 0)  # Skip empty lists

        engine = WorkflowEngine()

        workflow = Workflow(
            name="test-threshold",
            version="1.0.0",
            inputs={
                "companies": WorkflowInput(input_type="array", required=True),
                "threshold": WorkflowInput(input_type="number", required=True),
            },
            nodes={
                "split": Node(
                    name="split",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(
                        field="inputs.companies", item_name="company"
                    ),
                ),
                "filter": Node(
                    name="filter",
                    type=NodeType.FILTER,
                    depends_on=["split"],
                    config=FilterNodeConfig(
                        condition="{{ company.revenue > inputs.threshold }}"
                    ),
                ),
            },
        )

        context = await engine.execute(
            workflow, {"companies": companies, "threshold": threshold}
        )

        filtered = [f for f in context.outputs["filter"] if f is not None]

        # All filtered items should exceed threshold
        for item in filtered:
            assert item["revenue"] > threshold

        # No items exceeding threshold should be filtered out
        should_pass = [c for c in companies if c["revenue"] > threshold]
        assert len(should_pass) == len(filtered)
