"""Tests for schema validation between nodes"""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from seriesoftubes.engine import ExecutionContext, WorkflowEngine
from seriesoftubes.models import (
    HTTPNodeConfig,
    LLMNodeConfig,
    Node,
    NodeType,
    Workflow,
    WorkflowInput,
)
from seriesoftubes.nodes import NodeResult
from seriesoftubes.schemas import (
    HTTPNodeInput,
    HTTPNodeOutput,
    LLMNodeInput,
    LLMNodeOutput,
)


@pytest.fixture
def workflow_with_schemas():
    """Create a workflow with schema validation"""
    return Workflow(
        name="test_workflow_schemas",
        version="1.0",
        inputs={"company": WorkflowInput(required=True)},
        nodes={
            "search_api": Node(
                name="search_api",
                type=NodeType.HTTP,
                depends_on=[],
                config=HTTPNodeConfig(
                    url="https://api.example.com/search",
                    method="GET",
                    params={"q": "{{ inputs.company }}"},
                ),
            ),
            "analyze": Node(
                name="analyze",
                type=NodeType.LLM,
                depends_on=["search_api"],
                config=LLMNodeConfig(
                    prompt="Analyze this data: {{ search_data }}",
                    context={"search_data": "search_api"},
                ),
            ),
        },
        outputs={"analysis": "analyze"},
    )


class TestSchemaValidation:
    """Test schema validation functionality"""

    def test_input_schema_validation(self):
        """Test that input schemas are validated"""
        # Test LLM node input validation
        valid_input = {
            "prompt": "Test prompt",
            "model": "gpt-4",
            "temperature": 0.7,
        }
        
        # Should not raise
        LLMNodeInput(**valid_input)
        
        # Test invalid input
        with pytest.raises(ValidationError) as exc_info:
            LLMNodeInput(
                prompt=123,  # Should be string
                model="gpt-4",
            )
        assert "prompt" in str(exc_info.value)

    def test_output_schema_validation(self):
        """Test that output schemas are validated"""
        # Test HTTP node output validation
        valid_output = {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "body": {"results": []},
            "url": "https://api.example.com/search",
        }
        
        # Should not raise
        HTTPNodeOutput(**valid_output)
        
        # Test invalid output - Pydantic will coerce string to int
        # So let's test with an actually invalid type
        with pytest.raises(ValidationError) as exc_info:
            HTTPNodeOutput(
                # Missing required fields
                headers={},
                body={},
            )
        assert "status_code" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_runtime_validation_between_nodes(self, workflow_with_schemas):
        """Test that outputs are validated against downstream inputs"""
        engine = WorkflowEngine()
        
        # Mock the node executors to return specific outputs
        with patch.object(engine.executors[NodeType.HTTP], "execute") as mock_http, \
             patch.object(engine.executors[NodeType.LLM], "execute") as mock_llm:
            # Return None output which should trigger validation error
            mock_http.return_value = NodeResult(
                output=None,
                success=True,
            )
            
            # Mock LLM to avoid it failing due to None input
            mock_llm.return_value = NodeResult(
                output={"response": "dummy"},
                success=True,
            )
            
            context = await engine.execute(workflow_with_schemas, {"company": "Acme"})
            
            # Should have validation errors recorded
            assert "search_api" in context.validation_errors
            assert any("Output is None" in err for err in context.validation_errors["search_api"])

    @pytest.mark.asyncio
    async def test_valid_schema_flow(self, workflow_with_schemas):
        """Test that valid outputs pass validation"""
        engine = WorkflowEngine()
        
        with patch.object(engine.executors[NodeType.HTTP], "execute") as mock_http, \
             patch.object(engine.executors[NodeType.LLM], "execute") as mock_llm:
            
            # Return valid output that matches schema
            mock_http.return_value = NodeResult(
                output={
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": {"company": "Acme Corp", "revenue": 1000000},
                    "url": "https://api.example.com/search?q=Acme",
                },
                success=True,
            )
            
            mock_llm.return_value = NodeResult(
                output={
                    "response": "Analysis complete",
                    "model_used": "gpt-4",
                    "structured_output": None,
                    "token_usage": {"prompt": 100, "completion": 50},
                },
                success=True,
            )
            
            context = await engine.execute(workflow_with_schemas, {"company": "Acme"})
            
            # Should have no validation errors
            assert len(context.validation_errors) == 0
            assert context.errors == {}
            assert "search_api" in context.outputs
            assert "analyze" in context.outputs

    def test_schema_class_assignment(self):
        """Test that schema classes are properly assigned to executors"""
        from seriesoftubes.nodes import (
            FileNodeExecutor,
            HTTPNodeExecutor,
            LLMNodeExecutor,
            PythonNodeExecutor,
            RouteNodeExecutor,
        )
        
        # Check that each executor has schema classes assigned
        assert LLMNodeExecutor.input_schema_class is not None
        assert LLMNodeExecutor.output_schema_class is not None
        
        assert HTTPNodeExecutor.input_schema_class is not None
        assert HTTPNodeExecutor.output_schema_class is not None
        
        assert RouteNodeExecutor.input_schema_class is not None
        assert RouteNodeExecutor.output_schema_class is not None
        
        assert FileNodeExecutor.input_schema_class is not None
        assert FileNodeExecutor.output_schema_class is not None
        
        assert PythonNodeExecutor.input_schema_class is not None
        assert PythonNodeExecutor.output_schema_class is not None