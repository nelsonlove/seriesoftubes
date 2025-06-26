"""Test schema validation for data flow primitive nodes"""

import pytest
from pydantic import ValidationError

from seriesoftubes.schemas import (
    NODE_SCHEMAS,
    AggregateNodeInput,
    AggregateNodeOutput,
    ConditionalNodeInput,
    ConditionalNodeOutput,
    FilterNodeInput,
    FilterNodeOutput,
    ForeachNodeInput,
    ForeachNodeOutput,
    JoinNodeInput,
    JoinNodeOutput,
    SplitNodeInput,
    SplitNodeOutput,
    TransformNodeInput,
    TransformNodeOutput,
)


class TestDataFlowSchemas:
    """Test schema definitions and validation for data flow nodes"""

    def test_split_node_schemas(self):
        """Test split node input/output validation"""
        # Valid input
        valid_input = SplitNodeInput(array_data=[1, 2, 3])
        assert valid_input.array_data == [1, 2, 3]

        # Invalid input - missing required field
        with pytest.raises(ValidationError):
            SplitNodeInput()

        # Valid output
        valid_output = SplitNodeOutput(item="test", index=0, total=3)
        assert valid_output.item == "test"
        assert valid_output.index == 0
        assert valid_output.total == 3

    def test_aggregate_node_schemas(self):
        """Test aggregate node input/output validation"""
        # Valid input
        valid_input = AggregateNodeInput(items=[{"a": 1}, {"b": 2}])
        assert len(valid_input.items) == 2

        # Valid output
        valid_output = AggregateNodeOutput(result=[{"a": 1}, {"b": 2}], count=2)
        assert valid_output.count == 2

    def test_filter_node_schemas(self):
        """Test filter node input/output validation"""
        # Valid input
        valid_input = FilterNodeInput(items=[1, 2, 3], filter_context={"threshold": 2})
        assert valid_input.items == [1, 2, 3]
        assert valid_input.filter_context["threshold"] == 2

        # Valid output
        valid_output = FilterNodeOutput(filtered=[2, 3], removed_count=1)
        assert len(valid_output.filtered) == 2
        assert valid_output.removed_count == 1

    def test_transform_node_schemas(self):
        """Test transform node input/output validation"""
        # Valid input
        valid_input = TransformNodeInput(
            items=[{"name": "test"}], transform_context={"prefix": "X"}
        )
        assert len(valid_input.items) == 1

        # Valid output
        valid_output = TransformNodeOutput(
            transformed=[{"id": "X_test"}], transform_count=1
        )
        assert valid_output.transform_count == 1

    def test_join_node_schemas(self):
        """Test join node input/output validation"""
        # Valid input
        valid_input = JoinNodeInput(
            sources={"left": [{"id": 1}], "right": [{"id": 1, "value": "A"}]}
        )
        assert "left" in valid_input.sources
        assert "right" in valid_input.sources

        # Valid output
        valid_output = JoinNodeOutput(
            joined=[{"left_id": 1, "right_id": 1, "right_value": "A"}],
            source_counts={"left": 1, "right": 1},
        )
        assert valid_output.source_counts["left"] == 1

    def test_foreach_node_schemas(self):
        """Test foreach node input/output validation"""
        # Valid input
        valid_input = ForeachNodeInput(
            items=[1, 2, 3], foreach_context={"multiplier": 2}
        )
        assert len(valid_input.items) == 3

        # Valid output
        valid_output = ForeachNodeOutput(results=[2, 4, 6], execution_count=3)
        assert valid_output.execution_count == 3

    def test_conditional_node_schemas(self):
        """Test conditional node input/output validation"""
        # Valid input
        valid_input = ConditionalNodeInput(
            context_data={"score": 85, "status": "active"}
        )
        assert valid_input.context_data["score"] == 85

        # Valid output
        valid_output = ConditionalNodeOutput(
            selected_route="high_score_path",
            condition_met="score > 80",
            evaluated_conditions=["score > 80", "score > 90"],
        )
        assert valid_output.selected_route == "high_score_path"
        assert len(valid_output.evaluated_conditions) == 2

    def test_all_nodes_have_schemas(self):
        """Test that all data flow nodes are registered in NODE_SCHEMAS"""
        expected_nodes = [
            "split",
            "aggregate",
            "filter",
            "transform",
            "join",
            "foreach",
            "conditional",
            "llm",
            "http",
            "file",
            "python",
            "route",  # Including existing nodes
        ]

        for node_type in expected_nodes:
            assert (
                node_type in NODE_SCHEMAS
            ), f"Node type '{node_type}' missing from NODE_SCHEMAS"
            assert "input" in NODE_SCHEMAS[node_type]
            assert "output" in NODE_SCHEMAS[node_type]

            # Verify schema classes are valid
            input_schema = NODE_SCHEMAS[node_type]["input"]
            output_schema = NODE_SCHEMAS[node_type]["output"]
            assert hasattr(input_schema, "model_validate")
            assert hasattr(output_schema, "model_validate")

    def test_schema_inheritance(self):
        """Test that all schemas inherit from base classes"""
        # Import moved to test method to avoid circular import issues
        # ruff: noqa: PLC0415
        from seriesoftubes.schemas import NodeInputSchema, NodeOutputSchema

        # Test input schemas
        assert issubclass(SplitNodeInput, NodeInputSchema)
        assert issubclass(AggregateNodeInput, NodeInputSchema)
        assert issubclass(FilterNodeInput, NodeInputSchema)
        assert issubclass(TransformNodeInput, NodeInputSchema)
        assert issubclass(JoinNodeInput, NodeInputSchema)
        assert issubclass(ForeachNodeInput, NodeInputSchema)
        assert issubclass(ConditionalNodeInput, NodeInputSchema)

        # Test output schemas
        assert issubclass(SplitNodeOutput, NodeOutputSchema)
        assert issubclass(AggregateNodeOutput, NodeOutputSchema)
        assert issubclass(FilterNodeOutput, NodeOutputSchema)
        assert issubclass(TransformNodeOutput, NodeOutputSchema)
        assert issubclass(JoinNodeOutput, NodeOutputSchema)
        assert issubclass(ForeachNodeOutput, NodeOutputSchema)
        assert issubclass(ConditionalNodeOutput, NodeOutputSchema)
