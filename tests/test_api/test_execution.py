"""Tests for execution manager functionality"""

import asyncio

import pytest

from seriesoftubes.api.execution import execution_manager


@pytest.fixture
def sample_workflow(tmp_path):
    """Create a sample workflow file"""
    workflow_path = tmp_path / "test_workflow.yaml"
    workflow_path.write_text(
        """
name: test-api-workflow
version: "1.0"
description: Test workflow for API

inputs:
  message:
    type: string
    required: true

nodes:
  echo:
    type: conditional
    config:
      conditions:
        - is_default: true
          then: echo

outputs:
  result: echo
"""
    )
    return workflow_path


class TestExecutionManager:
    """Test execution manager functionality"""

    @pytest.mark.asyncio
    async def test_execution_tracking(self, sample_workflow):
        """Test that executions are properly tracked"""
        # Run a workflow
        execution_id = await execution_manager.run_workflow(
            sample_workflow, {"message": "test"}
        )

        # Check execution is tracked
        status = execution_manager.get_status(execution_id)
        assert status is not None
        assert status["id"] == execution_id
        assert status["workflow_name"] == "test-api-workflow"

        # Wait for completion
        await asyncio.sleep(0.5)

        # Check final status
        status = execution_manager.get_status(execution_id)
        assert status["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_execution_with_invalid_inputs(self, sample_workflow):
        """Test execution with invalid inputs"""
        # Run with missing required input
        execution_id = await execution_manager.run_workflow(sample_workflow, {})

        # Should record as failed
        await asyncio.sleep(0.5)
        status = execution_manager.get_status(execution_id)
        assert status["status"] == "failed"
        assert "error" in status or "errors" in status
