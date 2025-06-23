"""Tests for workflow parser"""

from pathlib import Path

import pytest

from seriesoftubes.models import NodeType
from seriesoftubes.parser import WorkflowParseError, parse_workflow_yaml, validate_dag


def test_parse_simple_workflow():
    """Test parsing a simple workflow"""
    workflow_path = Path("examples/simple-test/workflow.yaml")
    workflow = parse_workflow_yaml(workflow_path)

    # Check basic properties
    assert workflow.name == "simple-test"
    assert workflow.version == "1.0"
    assert workflow.description == "A simple test workflow"

    # Check inputs
    assert len(workflow.inputs) == 2
    assert "company_name" in workflow.inputs
    assert workflow.inputs["company_name"].required is True
    assert workflow.inputs["include_news"].default is False

    # Check nodes
    assert len(workflow.nodes) == 6
    assert workflow.nodes["classify_company"].node_type == NodeType.LLM
    assert workflow.nodes["fetch_data"].node_type == NodeType.HTTP
    assert workflow.nodes["decide_analysis"].node_type == NodeType.ROUTE

    # Check dependencies
    assert workflow.nodes["classify_company"].depends_on == []
    assert workflow.nodes["fetch_data"].depends_on == ["classify_company"]

    # Check outputs
    assert workflow.outputs["classification"] == "classify_company"
    assert workflow.outputs["analysis"] == "decide_analysis"


def test_validate_dag_simple():
    """Test DAG validation on valid workflow"""
    workflow_path = Path("examples/simple-test/workflow.yaml")
    workflow = parse_workflow_yaml(workflow_path)

    # Should not raise
    validate_dag(workflow)


def test_parse_invalid_yaml(tmp_path):
    """Test parsing invalid YAML"""
    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text("{ invalid yaml :")

    with pytest.raises(WorkflowParseError, match="Invalid YAML"):
        parse_workflow_yaml(invalid_yaml)


def test_missing_required_fields(tmp_path):
    """Test parsing with missing required fields"""
    incomplete_yaml = tmp_path / "incomplete.yaml"
    incomplete_yaml.write_text(
        """
name: incomplete
nodes:
  test_node:
    # Missing type
    config:
      prompt: "test"
"""
    )

    with pytest.raises(WorkflowParseError):
        parse_workflow_yaml(incomplete_yaml)


def test_cycle_detection(tmp_path):
    """Test cycle detection in DAG"""
    cycle_yaml = tmp_path / "cycle.yaml"
    cycle_yaml.write_text(
        """
name: cycle-test
nodes:
  node_a:
    type: llm
    depends_on: [node_b]
    config:
      prompt: "A"
  node_b:
    type: llm
    depends_on: [node_c]
    config:
      prompt: "B"
  node_c:
    type: llm
    depends_on: [node_a]  # Creates cycle
    config:
      prompt: "C"
"""
    )

    workflow = parse_workflow_yaml(cycle_yaml)
    with pytest.raises(WorkflowParseError, match="cycle"):
        validate_dag(workflow)


def test_nonexistent_dependency(tmp_path):
    """Test referencing non-existent node"""
    bad_dep_yaml = tmp_path / "bad_dep.yaml"
    bad_dep_yaml.write_text(
        """
name: bad-dep
nodes:
  node_a:
    type: llm
    depends_on: [node_that_does_not_exist]
    config:
      prompt: "A"
"""
    )

    workflow = parse_workflow_yaml(bad_dep_yaml)
    with pytest.raises(WorkflowParseError, match="non-existent node"):
        validate_dag(workflow)


def test_route_validation(tmp_path):
    """Test route node validation"""
    bad_route_yaml = tmp_path / "bad_route.yaml"
    bad_route_yaml.write_text(
        """
name: bad-route
nodes:
  router:
    type: route
    depends_on: []
    config:
      routes:
        - when: "true"
          to: nonexistent_node
        - default: true
          to: also_nonexistent
"""
    )

    workflow = parse_workflow_yaml(bad_route_yaml)
    with pytest.raises(WorkflowParseError, match="non-existent node"):
        validate_dag(workflow)
