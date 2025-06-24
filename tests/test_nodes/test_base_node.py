"""Tests for base node classes and models"""

from seriesoftubes.nodes import NodeResult


def test_node_result():
    """Test NodeResult model"""
    # Success result
    result = NodeResult(output={"key": "value"}, success=True)
    assert result.success
    assert result.output == {"key": "value"}
    assert result.error is None

    # Error result
    result = NodeResult(output=None, success=False, error="Something went wrong")
    assert not result.success
    assert result.error == "Something went wrong"

    # With metadata
    result = NodeResult(
        output="data",
        success=True,
        metadata={"execution_time": 1.5, "status_code": 200},
    )
    assert result.metadata["execution_time"] == 1.5
    assert result.metadata["status_code"] == 200
