"""Tests for join node functionality"""

import pytest

from seriesoftubes.engine import WorkflowEngine
from seriesoftubes.models import (
    JoinNodeConfig,
    Node,
    NodeType,
    Workflow,
    WorkflowInput,
)


@pytest.fixture
def engine():
    """Workflow engine instance"""
    return WorkflowEngine()


@pytest.fixture
def sample_data():
    """Sample data for join testing"""
    return {
        "employees": [
            {"id": 1, "name": "Alice", "dept_id": 10},
            {"id": 2, "name": "Bob", "dept_id": 20},
            {"id": 3, "name": "Charlie", "dept_id": 10},
        ],
        "departments": [
            {"id": 10, "name": "Engineering", "budget": 500000},
            {"id": 20, "name": "Marketing", "budget": 300000},
            {"id": 30, "name": "Sales", "budget": 400000},
        ],
    }


class TestJoinNode:
    """Test join node functionality"""

    @pytest.mark.asyncio
    async def test_inner_join(self, engine, sample_data):
        """Test inner join between two datasets"""
        workflow = Workflow(
            name="test-inner-join",
            version="1.0.0",
            inputs={
                "employees": WorkflowInput(input_type="array", required=True),
                "departments": WorkflowInput(input_type="array", required=True),
            },
            nodes={
                "join_emp_dept": Node(
                    name="join_emp_dept",
                    type=NodeType.JOIN,
                    config=JoinNodeConfig(
                        sources={
                            "employees": "inputs.employees",
                            "departments": "inputs.departments",
                        },
                        join_type="inner",
                        join_keys={"dept_id": "id"},
                    ),
                )
            },
            outputs={"result": "join_emp_dept"},
        )

        context = await engine.execute(workflow, sample_data)

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["join_emp_dept"]

        # Should have 3 records (all employees have matching departments)
        assert isinstance(result, list)
        assert len(result) == 3

        # Verify join structure
        for record in result:
            assert "employees" in record
            assert "departments" in record
            assert record["employees"]["dept_id"] == record["departments"]["id"]

    @pytest.mark.asyncio
    async def test_left_join(self, engine):
        """Test left join with unmatched records"""
        employees = [
            {"id": 1, "name": "Alice", "dept_id": 10},
            {"id": 2, "name": "Bob", "dept_id": 99},  # No matching department
        ]
        departments = [{"id": 10, "name": "Engineering", "budget": 500000}]

        workflow = Workflow(
            name="test-left-join",
            version="1.0.0",
            inputs={
                "employees": WorkflowInput(input_type="array", required=True),
                "departments": WorkflowInput(input_type="array", required=True),
            },
            nodes={
                "join_left": Node(
                    name="join_left",
                    type=NodeType.JOIN,
                    config=JoinNodeConfig(
                        sources={
                            "employees": "inputs.employees",
                            "departments": "inputs.departments",
                        },
                        join_type="left",
                        join_keys={"dept_id": "id"},
                    ),
                )
            },
            outputs={"result": "join_left"},
        )

        context = await engine.execute(workflow, {"employees": employees, "departments": departments})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["join_left"]

        # Should have 2 records (all employees, with Bob having null department)
        assert len(result) == 2

        alice = next(r for r in result if r["employees"]["name"] == "Alice")
        bob = next(r for r in result if r["employees"]["name"] == "Bob")

        assert alice["departments"] is not None
        assert bob["departments"] is None

    @pytest.mark.asyncio
    async def test_cross_join(self, engine):
        """Test cross join (cartesian product)"""
        small_employees = [{"id": 1, "name": "Alice"}]
        small_departments = [{"id": 10, "name": "Eng"}, {"id": 20, "name": "Marketing"}]

        workflow = Workflow(
            name="test-cross-join",
            version="1.0.0",
            inputs={
                "employees": WorkflowInput(input_type="array", required=True),
                "departments": WorkflowInput(input_type="array", required=True),
            },
            nodes={
                "join_cross": Node(
                    name="join_cross",
                    type=NodeType.JOIN,
                    config=JoinNodeConfig(
                        sources={
                            "employees": "inputs.employees",
                            "departments": "inputs.departments",
                        },
                        join_type="cross",
                    ),
                )
            },
            outputs={"result": "join_cross"},
        )

        context = await engine.execute(workflow, {"employees": small_employees, "departments": small_departments})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["join_cross"]

        # Should have 1 * 2 = 2 records
        assert len(result) == 2

        # All combinations should be present
        for record in result:
            assert record["employees"]["name"] == "Alice"
            assert record["departments"]["name"] in ["Eng", "Marketing"]

    @pytest.mark.asyncio
    async def test_merge_join(self, engine):
        """Test merge join (combines matching records)"""
        users = [
            {"user_id": 1, "username": "alice", "email": "alice@example.com"},
            {"user_id": 2, "username": "bob", "email": "bob@example.com"},
        ]
        profiles = [
            {"user_id": 1, "bio": "Software engineer", "location": "SF"},
            {"user_id": 2, "bio": "Designer", "location": "NYC"},
        ]

        workflow = Workflow(
            name="test-merge-join",
            version="1.0.0",
            inputs={
                "users": WorkflowInput(input_type="array", required=True),
                "profiles": WorkflowInput(input_type="array", required=True),
            },
            nodes={
                "join_merge": Node(
                    name="join_merge",
                    type=NodeType.JOIN,
                    config=JoinNodeConfig(
                        sources={
                            "users": "inputs.users",
                            "profiles": "inputs.profiles",
                        },
                        join_type="merge",
                        join_keys={"user_id": "user_id"},
                    ),
                )
            },
            outputs={"result": "join_merge"},
        )

        context = await engine.execute(workflow, {"users": users, "profiles": profiles})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["join_merge"]

        assert len(result) == 2

        # Records should be merged, not nested
        for record in result:
            assert "user_id" in record
            assert "username" in record
            assert "email" in record
            assert "bio" in record
            assert "location" in record

    @pytest.mark.asyncio
    async def test_multiple_join_keys(self, engine):
        """Test join with multiple key conditions"""
        orders = [
            {"order_id": 1, "customer_id": 100, "region": "US"},
            {"order_id": 2, "customer_id": 101, "region": "EU"},
        ]
        pricing = [
            {"customer_id": 100, "region": "US", "discount": 0.1},
            {"customer_id": 101, "region": "EU", "discount": 0.15},
        ]

        workflow = Workflow(
            name="test-multi-key-join",
            version="1.0.0",
            inputs={
                "orders": WorkflowInput(input_type="array", required=True),
                "pricing": WorkflowInput(input_type="array", required=True),
            },
            nodes={
                "join_multi": Node(
                    name="join_multi",
                    type=NodeType.JOIN,
                    config=JoinNodeConfig(
                        sources={
                            "orders": "inputs.orders",
                            "pricing": "inputs.pricing",
                        },
                        join_type="inner",
                        join_keys={"customer_id": "customer_id", "region": "region"},
                    ),
                )
            },
            outputs={"result": "join_multi"},
        )

        context = await engine.execute(workflow, {"orders": orders, "pricing": pricing})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["join_multi"]

        assert len(result) == 2

        for record in result:
            assert record["orders"]["customer_id"] == record["pricing"]["customer_id"]
            assert record["orders"]["region"] == record["pricing"]["region"]

    @pytest.mark.asyncio
    async def test_join_error_handling(self, engine):
        """Test error handling in join operations"""
        workflow = Workflow(
            name="test-join-error",
            version="1.0.0",
            inputs={
                "data1": WorkflowInput(input_type="array", required=True),
                "data2": WorkflowInput(input_type="array", required=True),
            },
            nodes={
                "join_invalid": Node(
                    name="join_invalid",
                    type=NodeType.JOIN,
                    config=JoinNodeConfig(
                        sources={
                            "data1": "inputs.nonexistent",  # Invalid source
                            "data2": "inputs.data2",
                        },
                        join_type="inner",
                        join_keys={"id": "id"},
                    ),
                )
            },
            outputs={"result": "join_invalid"},
        )

        context = await engine.execute(workflow, {"data1": [], "data2": []})

        # Should have errors
        assert len(context.errors) > 0
        assert "join_invalid" in context.errors