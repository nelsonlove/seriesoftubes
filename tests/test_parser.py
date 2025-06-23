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
    assert workflow.inputs["include_news"].required is False  # Has default, so not required

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


def test_input_with_default_not_required(tmp_path):
    """Test that inputs with defaults are automatically not required"""
    test_yaml = tmp_path / "test_defaults.yaml"
    test_yaml.write_text(
        """
name: test-defaults
inputs:
  with_default:
    type: string
    default: "hello"
  without_default:
    type: string
  explicit_required:
    type: string
    required: true
    default: "world"
  boolean_default:
    type: boolean
    default: false
nodes:
  dummy:
    type: route
    config:
      routes:
        - default: true
          to: dummy
"""
    )

    workflow = parse_workflow_yaml(test_yaml)
    
    # Input with default should not be required
    assert not workflow.inputs["with_default"].required
    assert workflow.inputs["with_default"].default == "hello"
    
    # Input without default should be required
    assert workflow.inputs["without_default"].required
    assert workflow.inputs["without_default"].default is None
    
    # Even if explicitly marked required, having a default makes it not required
    assert not workflow.inputs["explicit_required"].required
    assert workflow.inputs["explicit_required"].default == "world"
    
    # Boolean default should also work
    assert not workflow.inputs["boolean_default"].required
    assert workflow.inputs["boolean_default"].default is False
