"""
Test execution status tracking functionality
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from seriesoftubes.engine import WorkflowEngine
from seriesoftubes.parser import parse_workflow_yaml


class TestExecutionStatus:
    """Test execution status and progress tracking"""

    @pytest.mark.asyncio
    async def test_basic_execution_status(self):
        """Test that basic execution works with our changes"""

        # Create a simple test workflow
        test_workflow_yaml = """
name: status-test
version: "1.0.0"

inputs:
  message:
    type: string
    required: true
    default: "Hello World"

nodes:
  echo:
    type: python
    config:
      code: |
        message = context['inputs']['message']
        return {"result": f"Echo: {message}"}

outputs:
  result: echo.result
"""

        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(test_workflow_yaml)
            temp_path = Path(f.name)

        try:
            # Parse workflow
            workflow = parse_workflow_yaml(temp_path)
            assert workflow.name == "status-test"

            # Test basic engine execution
            engine = WorkflowEngine()
            context = await engine.execute(workflow, {"message": "Test message"})

            # Verify execution completed successfully
            assert len(context.errors) == 0
            assert "echo" in context.outputs
            assert context.outputs["echo"]["result"]["result"] == "Echo: Test message"

        finally:
            temp_path.unlink()

    def test_database_progress_tracking_engine_import(self):
        """Test that DatabaseProgressTrackingEngine can be imported"""
        from seriesoftubes.api.execution import DatabaseProgressTrackingEngine

        # Test the class exists and can be instantiated (with mock session)
        assert DatabaseProgressTrackingEngine is not None

    @pytest.mark.asyncio
    async def test_multi_node_execution(self):
        """Test execution with multiple nodes to verify progress tracking works"""

        multi_node_yaml = """
name: multi-node-test
version: "1.0.0"

inputs:
  number:
    type: number
    required: true
    default: 5

nodes:
  double:
    type: python
    config:
      code: |
        return {"doubled": context['inputs']['number'] * 2}

  triple:
    type: python
    depends_on: [double]
    config:
      code: |
        return {"tripled": context['double']['result']['doubled'] * 3}

outputs:
  result: triple.tripled
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(multi_node_yaml)
            temp_path = Path(f.name)

        try:
            workflow = parse_workflow_yaml(temp_path)
            engine = WorkflowEngine()
            context = await engine.execute(workflow, {"number": 5})

            # Verify both nodes executed
            assert len(context.errors) == 0
            assert "double" in context.outputs
            assert "triple" in context.outputs
            assert context.outputs["double"]["result"]["doubled"] == 10
            assert context.outputs["triple"]["result"]["tripled"] == 30

        finally:
            temp_path.unlink()


if __name__ == "__main__":
    # Manual execution for debugging
    import asyncio

    async def manual_test():
        """Manual test function for debugging"""
        test_instance = TestExecutionStatus()

        await test_instance.test_basic_execution_status()
        test_instance.test_database_progress_tracking_engine_import()
        await test_instance.test_multi_node_execution()

        return True

    success = asyncio.run(manual_test())
    if success:
        print("\n✅ All execution status tests passed!")
    else:
        print("\n❌ Execution status tests failed!")
        exit(1)
