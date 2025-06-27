"""Tests for aggregate node functionality"""

import pytest
from pydantic import ValidationError

from seriesoftubes.engine import WorkflowEngine
from seriesoftubes.models import (
    AggregateNodeConfig,
    FilterNodeConfig,
    Node,
    NodeType,
    SplitNodeConfig,
    TransformNodeConfig,
    Workflow,
    WorkflowInput,
)


@pytest.fixture
def engine():
    """Workflow engine instance"""
    return WorkflowEngine()


@pytest.fixture
def sample_data():
    """Sample data for aggregate testing"""
    return [
        {"id": 1, "name": "Alice", "category": "A", "value": 100},
        {"id": 2, "name": "Bob", "category": "B", "value": 200},
        {"id": 3, "name": "Charlie", "category": "A", "value": 150},
        {"id": 4, "name": "Diana", "category": "C", "value": 75},
    ]


class TestAggregateNode:
    """Test aggregate node functionality"""

    @pytest.mark.asyncio
    async def test_aggregate_array_mode(self, engine, sample_data):
        """Test aggregation in array mode"""
        workflow = Workflow(
            name="test-aggregate-array",
            version="1.0.0",
            inputs={"items": WorkflowInput(input_type="array", required=True)},
            nodes={
                "split_items": Node(
                    name="split_items",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(field="inputs.items", item_name="item"),
                ),
                "filter_high_value": Node(
                    name="filter_high_value",
                    type=NodeType.FILTER,
                    depends_on=["split_items"],
                    config=FilterNodeConfig(condition="{{ item.value > 100 }}"),
                ),
                "aggregate_array": Node(
                    name="aggregate_array",
                    type=NodeType.AGGREGATE,
                    depends_on=["filter_high_value"],
                    config=AggregateNodeConfig(mode="array"),
                ),
            },
            outputs={"high_value_items": "aggregate_array"},
        )

        context = await engine.execute(workflow, {"items": sample_data})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["aggregate_array"]

        assert isinstance(result, list)
        assert len(result) == 4  # Includes None for filtered out items

        # Count non-None items (should be 2: Bob=200, Charlie=150)
        high_value_items = [item for item in result if item is not None]
        assert len(high_value_items) == 2

        # Verify all high-value items
        values = [item["value"] for item in high_value_items]
        assert all(value > 100 for value in values)

    @pytest.mark.asyncio
    async def test_aggregate_object_mode(self, engine, sample_data):
        """Test aggregation in object mode"""
        workflow = Workflow(
            name="test-aggregate-object",
            version="1.0.0",
            inputs={"items": WorkflowInput(input_type="array", required=True)},
            nodes={
                "split_items": Node(
                    name="split_items",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(field="inputs.items", item_name="item"),
                ),
                "transform_items": Node(
                    name="transform_items",
                    type=NodeType.TRANSFORM,
                    depends_on=["split_items"],
                    config=TransformNodeConfig(
                        template={
                            "id": "{{ item.id }}",
                            "display_name": "{{ item.name }} ({{ item.category }})",
                            "doubled_value": "{{ item.value * 2 }}",
                        }
                    ),
                ),
                "aggregate_object": Node(
                    name="aggregate_object",
                    type=NodeType.AGGREGATE,
                    depends_on=["transform_items"],
                    config=AggregateNodeConfig(mode="object"),
                ),
            },
            outputs={"transformed_object": "aggregate_object"},
        )

        context = await engine.execute(workflow, {"items": sample_data})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["aggregate_object"]

        assert isinstance(result, dict)
        assert len(result) == 4  # Keys: "0", "1", "2", "3"

        # Verify object structure
        for key in ["0", "1", "2", "3"]:
            assert key in result
            item = result[key]
            assert "id" in item
            assert "display_name" in item
            assert "doubled_value" in item

        # Verify transformations
        alice = result["0"]
        assert alice["display_name"] == "Alice (A)"
        assert alice["doubled_value"] == 200

    @pytest.mark.asyncio
    async def test_aggregate_merge_mode(self, engine):
        """Test aggregation in merge mode"""
        simple_data = [
            {"user_id": 1, "score": 85},
            {"user_id": 2, "score": 92},
        ]

        workflow = Workflow(
            name="test-aggregate-merge",
            version="1.0.0",
            inputs={"items": WorkflowInput(input_type="array", required=True)},
            nodes={
                "split_items": Node(
                    name="split_items",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(field="inputs.items", item_name="item"),
                ),
                "transform_items": Node(
                    name="transform_items",
                    type=NodeType.TRANSFORM,
                    depends_on=["split_items"],
                    config=TransformNodeConfig(
                        template={
                            "user_id": "{{ item.user_id }}",
                            "grade": "{% if item.score >= 90 %}A{% else %}B{% endif %}",
                        }
                    ),
                ),
                "aggregate_merge": Node(
                    name="aggregate_merge",
                    type=NodeType.AGGREGATE,
                    depends_on=["transform_items"],
                    config=AggregateNodeConfig(mode="merge"),
                ),
            },
            outputs={"merged_result": "aggregate_merge"},
        )

        context = await engine.execute(workflow, {"items": simple_data})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["aggregate_merge"]

        assert isinstance(result, dict)

        # Should have merged keys with index prefixes
        assert "0_user_id" in result
        assert "0_grade" in result
        assert "1_user_id" in result
        assert "1_grade" in result

        assert result["0_user_id"] == 1
        assert result["0_grade"] == "B"  # 85 < 90
        assert result["1_user_id"] == 2
        assert result["1_grade"] == "A"  # 92 >= 90

    @pytest.mark.asyncio
    async def test_aggregate_with_field_extraction(self, engine, sample_data):
        """Test aggregation with field extraction"""
        workflow = Workflow(
            name="test-aggregate-field",
            version="1.0.0",
            inputs={"items": WorkflowInput(input_type="array", required=True)},
            nodes={
                "split_items": Node(
                    name="split_items",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(field="inputs.items", item_name="item"),
                ),
                "transform_items": Node(
                    name="transform_items",
                    type=NodeType.TRANSFORM,
                    depends_on=["split_items"],
                    config=TransformNodeConfig(
                        template={
                            "id": "{{ item.id }}",
                            "display_name": "{{ item.name }}",
                            "category_upper": "{{ item.category | upper }}",
                        }
                    ),
                ),
                "aggregate_names_only": Node(
                    name="aggregate_names_only",
                    type=NodeType.AGGREGATE,
                    depends_on=["transform_items"],
                    config=AggregateNodeConfig(mode="array", field="display_name"),
                ),
            },
            outputs={"names": "aggregate_names_only"},
        )

        context = await engine.execute(workflow, {"items": sample_data})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        names = context.outputs["aggregate_names_only"]

        assert isinstance(names, list)
        assert len(names) == 4

        # Should extract only the display_name field
        expected_names = ["Alice", "Bob", "Charlie", "Diana"]
        assert names == expected_names

    @pytest.mark.asyncio
    async def test_aggregate_with_missing_field(self, engine, sample_data):
        """Test aggregation with field that doesn't exist"""
        workflow = Workflow(
            name="test-aggregate-missing-field",
            version="1.0.0",
            inputs={"items": WorkflowInput(input_type="array", required=True)},
            nodes={
                "split_items": Node(
                    name="split_items",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(field="inputs.items", item_name="item"),
                ),
                "transform_items": Node(
                    name="transform_items",
                    type=NodeType.TRANSFORM,
                    depends_on=["split_items"],
                    config=TransformNodeConfig(
                        template={
                            "name": "{{ item.name }}",
                            "value": "{{ item.value }}",
                        }
                    ),
                ),
                "aggregate_missing": Node(
                    name="aggregate_missing",
                    type=NodeType.AGGREGATE,
                    depends_on=["transform_items"],
                    config=AggregateNodeConfig(mode="array", field="nonexistent_field"),
                ),
            },
            outputs={"result": "aggregate_missing"},
        )

        context = await engine.execute(workflow, {"items": sample_data})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["aggregate_missing"]

        # Should return array of None values (field doesn't exist)
        assert isinstance(result, list)
        assert len(result) == 4
        assert all(item is None for item in result)

    @pytest.mark.asyncio
    async def test_aggregate_empty_input(self, engine):
        """Test aggregation with empty input"""
        workflow = Workflow(
            name="test-aggregate-empty",
            version="1.0.0",
            inputs={"items": WorkflowInput(input_type="array", required=True)},
            nodes={
                "split_items": Node(
                    name="split_items",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(field="inputs.items", item_name="item"),
                ),
                "aggregate_empty": Node(
                    name="aggregate_empty",
                    type=NodeType.AGGREGATE,
                    depends_on=["split_items"],
                    config=AggregateNodeConfig(mode="array"),
                ),
            },
            outputs={"result": "aggregate_empty"},
        )

        context = await engine.execute(workflow, {"items": []})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["aggregate_empty"]

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_aggregate_complex_pipeline(self, engine):
        """Test aggregation in complex split-filter-transform-aggregate pipeline"""
        sales_data = [
            {"region": "North", "product": "A", "sales": 1000, "quarter": "Q1"},
            {"region": "South", "product": "B", "sales": 1500, "quarter": "Q1"},
            {"region": "North", "product": "A", "sales": 800, "quarter": "Q2"},
            {"region": "East", "product": "C", "sales": 2000, "quarter": "Q1"},
            {"region": "South", "product": "B", "sales": 500, "quarter": "Q2"},
        ]

        workflow = Workflow(
            name="test-complex-aggregate",
            version="1.0.0",
            inputs={"sales": WorkflowInput(input_type="array", required=True)},
            nodes={
                "split_sales": Node(
                    name="split_sales",
                    type=NodeType.SPLIT,
                    config=SplitNodeConfig(field="inputs.sales", item_name="sale"),
                ),
                "filter_high_sales": Node(
                    name="filter_high_sales",
                    type=NodeType.FILTER,
                    depends_on=["split_sales"],
                    config=FilterNodeConfig(condition="{{ sale.sales > 1000 }}"),
                ),
                "transform_sales": Node(
                    name="transform_sales",
                    type=NodeType.TRANSFORM,
                    depends_on=["filter_high_sales"],
                    config=TransformNodeConfig(
                        template={
                            "region": "{{ item.region }}",
                            "product": "{{ item.product }}",
                            "sales_k": "{{ (item.sales / 1000) | round(1) }}",
                            "performance": "{% if item.sales > 1500 %}excellent{% else %}good{% endif %}",
                        }
                    ),
                ),
                "aggregate_final": Node(
                    name="aggregate_final",
                    type=NodeType.AGGREGATE,
                    depends_on=["transform_sales"],
                    config=AggregateNodeConfig(mode="array"),
                ),
            },
            outputs={"high_performing_sales": "aggregate_final"},
        )

        context = await engine.execute(workflow, {"sales": sales_data})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["aggregate_final"]

        # Should have filtered to sales > 1000: South/B (1500), East/C (2000)
        high_sales = [item for item in result if item is not None]
        assert len(high_sales) == 2

        # Verify transformations
        excellent_sales = [s for s in high_sales if s["performance"] == "excellent"]
        good_sales = [s for s in high_sales if s["performance"] == "good"]

        assert len(excellent_sales) == 1  # East/C with 2000 sales
        assert len(good_sales) == 1  # South/B with 1500 sales

        assert excellent_sales[0]["sales_k"] == 2.0
        assert good_sales[0]["sales_k"] == 1.5

    @pytest.mark.asyncio
    async def test_aggregate_error_handling(self, engine):
        """Test error handling in aggregate operations"""
        workflow = Workflow(
            name="test-aggregate-error",
            version="1.0.0",
            inputs={"items": WorkflowInput(input_type="array", required=True)},
            nodes={
                "aggregate_invalid": Node(
                    name="aggregate_invalid",
                    type=NodeType.AGGREGATE,
                    depends_on=["nonexistent_node"],  # Invalid dependency
                    config=AggregateNodeConfig(mode="array"),
                ),
            },
            outputs={"result": "aggregate_invalid"},
        )

        context = await engine.execute(workflow, {"items": []})

        # Should have errors due to missing dependency
        assert len(context.errors) > 0
        assert "aggregate_invalid" in context.errors

    def test_aggregate_invalid_mode(self):
        """Test aggregate with invalid mode"""
        # Should raise ValidationError during config validation
        with pytest.raises(ValidationError, match="Mode must be one of"):
            AggregateNodeConfig(mode="invalid_mode")
