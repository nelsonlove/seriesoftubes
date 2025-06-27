"""Tests for foreach node functionality"""

import pytest

from seriesoftubes.engine import WorkflowEngine
from seriesoftubes.models import (
    ForEachNodeConfig,
    Node,
    NodeType,
    PythonNodeConfig,
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
    """Sample data for foreach testing"""
    return {
        "users": [
            {"id": 1, "name": "Alice", "score": 85},
            {"id": 2, "name": "Bob", "score": 92},
            {"id": 3, "name": "Charlie", "score": 78},
        ]
    }


class TestForEachNode:
    """Test foreach node functionality"""

    @pytest.mark.asyncio
    async def test_foreach_basic_iteration(self, engine, sample_data):
        """Test basic foreach iteration over array"""
        workflow = Workflow(
            name="test-foreach-basic",
            version="1.0.0",
            inputs={"users": WorkflowInput(input_type="array", required=True)},
            nodes={
                "process_users": Node(
                    name="process_users",
                    type=NodeType.FOREACH,
                    config=ForEachNodeConfig(
                        array_field="inputs.users",
                        item_name="user",
                        subgraph_nodes=["grade_user"],
                        parallel=False,
                    ),
                ),
                "grade_user": Node(
                    name="grade_user",
                    type=NodeType.TRANSFORM,
                    config=TransformNodeConfig(
                        template={
                            "id": "{{ user.id }}",
                            "name": "{{ user.name }}",
                            "grade": "{% if user.score >= 90 %}A{% elif user.score >= 80 %}B{% else %}C{% endif %}",
                        }
                    ),
                ),
            },
            outputs={"graded_users": "process_users"},
        )

        context = await engine.execute(workflow, sample_data)

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["process_users"]

        assert isinstance(result, list)
        assert len(result) == 3

        # Verify transformations
        grades = {user["name"]: user["grade"] for user in result}
        assert grades["Alice"] == "B"  # 85 -> B
        assert grades["Bob"] == "A"    # 92 -> A
        assert grades["Charlie"] == "C"  # 78 -> C

    @pytest.mark.asyncio
    async def test_foreach_parallel_execution(self, engine, sample_data):
        """Test foreach with parallel execution"""
        workflow = Workflow(
            name="test-foreach-parallel",
            version="1.0.0",
            inputs={"users": WorkflowInput(input_type="array", required=True)},
            nodes={
                "process_parallel": Node(
                    name="process_parallel",
                    type=NodeType.FOREACH,
                    config=ForEachNodeConfig(
                        array_field="inputs.users",
                        item_name="user",
                        subgraph_nodes=["calculate_bonus"],
                        parallel=True,
                    ),
                ),
                "calculate_bonus": Node(
                    name="calculate_bonus",
                    type=NodeType.PYTHON,
                    config=PythonNodeConfig(
                        code="""
score = context['user']['score']
base_bonus = 1000

# Calculate bonus based on score
if score >= 90:
    bonus = base_bonus * 1.5
elif score >= 80:
    bonus = base_bonus * 1.2
else:
    bonus = base_bonus

return {
    'user_id': context['user']['id'],
    'name': context['user']['name'],
    'score': score,
    'bonus': int(bonus)
}
""",
                        context={"user": "user"},
                    ),
                ),
            },
            outputs={"bonuses": "process_parallel"},
        )

        context = await engine.execute(workflow, sample_data)

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["process_parallel"]

        assert len(result) == 3

        # Verify bonus calculations
        bonuses = {user["name"]: user["bonus"] for user in result}
        assert bonuses["Alice"] == 1200  # 85 -> 1.2x bonus
        assert bonuses["Bob"] == 1500    # 92 -> 1.5x bonus
        assert bonuses["Charlie"] == 1000  # 78 -> 1.0x bonus

    @pytest.mark.asyncio
    async def test_foreach_multiple_subgraph_nodes(self, engine):
        """Test foreach with multiple nodes in subgraph"""
        documents = [
            {"id": 1, "title": "Document A", "words": 100},
            {"id": 2, "title": "Document B", "words": 250},
        ]

        workflow = Workflow(
            name="test-foreach-multi-nodes",
            version="1.0.0",
            inputs={"documents": WorkflowInput(input_type="array", required=True)},
            nodes={
                "process_documents": Node(
                    name="process_documents",
                    type=NodeType.FOREACH,
                    config=ForEachNodeConfig(
                        array_field="inputs.documents",
                        item_name="doc",
                        subgraph_nodes=["calculate_reading_time", "categorize_doc"],
                        parallel=False,
                    ),
                ),
                "calculate_reading_time": Node(
                    name="calculate_reading_time",
                    type=NodeType.PYTHON,
                    config=PythonNodeConfig(
                        code="""
words = context['doc']['words']
# Assume 200 words per minute reading speed
reading_time = max(1, round(words / 200))
return {
    'id': context['doc']['id'],
    'title': context['doc']['title'],
    'words': words,
    'reading_time_minutes': reading_time
}
""",
                        context={"doc": "doc"},
                    ),
                ),
                "categorize_doc": Node(
                    name="categorize_doc",
                    type=NodeType.TRANSFORM,
                    depends_on=["calculate_reading_time"],
                    config=TransformNodeConfig(
                        template={
                            "id": "{{ calculate_reading_time.id }}",
                            "title": "{{ calculate_reading_time.title }}",
                            "reading_time": "{{ calculate_reading_time.reading_time_minutes }}",
                            "category": "{% if calculate_reading_time.reading_time_minutes <= 1 %}quick{% elif calculate_reading_time.reading_time_minutes <= 3 %}medium{% else %}long{% endif %}",
                        }
                    ),
                ),
            },
            outputs={"processed_docs": "process_documents"},
        )

        context = await engine.execute(workflow, {"documents": documents})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["process_documents"]

        assert len(result) == 2

        # Verify processing pipeline
        doc_a = next(d for d in result if d["title"] == "Document A")
        doc_b = next(d for d in result if d["title"] == "Document B")

        assert doc_a["reading_time"] == 1  # 100 words -> 1 minute
        assert doc_a["category"] == "quick"

        assert doc_b["reading_time"] == 1  # 250 words -> 1.25 -> rounded to 1
        assert doc_b["category"] == "quick"

    @pytest.mark.asyncio
    async def test_foreach_empty_array(self, engine):
        """Test foreach with empty array"""
        workflow = Workflow(
            name="test-foreach-empty",
            version="1.0.0",
            inputs={"items": WorkflowInput(input_type="array", required=True)},
            nodes={
                "process_empty": Node(
                    name="process_empty",
                    type=NodeType.FOREACH,
                    config=ForEachNodeConfig(
                        array_field="inputs.items",
                        item_name="item",
                        subgraph_nodes=["transform_item"],
                        parallel=False,
                    ),
                ),
                "transform_item": Node(
                    name="transform_item",
                    type=NodeType.TRANSFORM,
                    config=TransformNodeConfig(template={"value": "{{ item.value }}"}),
                ),
            },
            outputs={"result": "process_empty"},
        )

        context = await engine.execute(workflow, {"items": []})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["process_empty"]

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_foreach_nested_data(self, engine):
        """Test foreach with nested data structures"""
        orders = [
            {
                "order_id": 1,
                "customer": "Alice",
                "items": [
                    {"product": "Laptop", "price": 1000, "qty": 1},
                    {"product": "Mouse", "price": 50, "qty": 2},
                ],
            },
            {
                "order_id": 2,
                "customer": "Bob",
                "items": [
                    {"product": "Keyboard", "price": 100, "qty": 1},
                ],
            },
        ]

        workflow = Workflow(
            name="test-foreach-nested",
            version="1.0.0",
            inputs={"orders": WorkflowInput(input_type="array", required=True)},
            nodes={
                "calculate_totals": Node(
                    name="calculate_totals",
                    type=NodeType.FOREACH,
                    config=ForEachNodeConfig(
                        array_field="inputs.orders",
                        item_name="order",
                        subgraph_nodes=["sum_order"],
                        parallel=False,
                    ),
                ),
                "sum_order": Node(
                    name="sum_order",
                    type=NodeType.PYTHON,
                    config=PythonNodeConfig(
                        code="""
order = context['order']
total = sum(item['price'] * item['qty'] for item in order['items'])
return {
    'order_id': order['order_id'],
    'customer': order['customer'],
    'total': total,
    'item_count': len(order['items'])
}
""",
                        context={"order": "order"},
                    ),
                ),
            },
            outputs={"order_totals": "calculate_totals"},
        )

        context = await engine.execute(workflow, {"orders": orders})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["calculate_totals"]

        assert len(result) == 2

        alice_order = next(o for o in result if o["customer"] == "Alice")
        bob_order = next(o for o in result if o["customer"] == "Bob")

        assert alice_order["total"] == 1100  # 1000 + (50 * 2)
        assert alice_order["item_count"] == 2

        assert bob_order["total"] == 100
        assert bob_order["item_count"] == 1

    @pytest.mark.asyncio
    async def test_foreach_error_handling(self, engine):
        """Test error handling in foreach operations"""
        workflow = Workflow(
            name="test-foreach-error",
            version="1.0.0",
            inputs={"items": WorkflowInput(input_type="array", required=True)},
            nodes={
                "process_with_error": Node(
                    name="process_with_error",
                    type=NodeType.FOREACH,
                    config=ForEachNodeConfig(
                        array_field="inputs.nonexistent",  # Invalid field
                        item_name="item",
                        subgraph_nodes=["transform_item"],
                        parallel=False,
                    ),
                ),
                "transform_item": Node(
                    name="transform_item",
                    type=NodeType.TRANSFORM,
                    config=TransformNodeConfig(template={"value": "{{ item.value }}"}),
                ),
            },
            outputs={"result": "process_with_error"},
        )

        context = await engine.execute(workflow, {"items": [{"value": 1}]})

        # Should have errors
        assert len(context.errors) > 0
        assert "process_with_error" in context.errors

    @pytest.mark.asyncio
    async def test_foreach_with_context_access(self, engine):
        """Test foreach with access to workflow inputs and other context"""
        workflow = Workflow(
            name="test-foreach-context",
            version="1.0.0",
            inputs={
                "items": WorkflowInput(input_type="array", required=True),
                "multiplier": WorkflowInput(input_type="number", required=True),
            },
            nodes={
                "multiply_items": Node(
                    name="multiply_items",
                    type=NodeType.FOREACH,
                    config=ForEachNodeConfig(
                        array_field="inputs.items",
                        item_name="item",
                        subgraph_nodes=["apply_multiplier"],
                        parallel=False,
                    ),
                ),
                "apply_multiplier": Node(
                    name="apply_multiplier",
                    type=NodeType.PYTHON,
                    config=PythonNodeConfig(
                        code="""
item_value = context['item']['value']
multiplier = context['inputs']['multiplier']
return {
    'original': item_value,
    'multiplied': item_value * multiplier
}
""",
                        context={"item": "item", "inputs": "inputs"},
                    ),
                ),
            },
            outputs={"multiplied_items": "multiply_items"},
        )

        items = [{"value": 10}, {"value": 20}, {"value": 30}]
        context = await engine.execute(workflow, {"items": items, "multiplier": 3})

        assert len(context.errors) == 0, f"Execution errors: {context.errors}"
        result = context.outputs["multiply_items"]

        assert len(result) == 3
        for i, item in enumerate(result):
            expected_original = items[i]["value"]
            assert item["original"] == expected_original
            assert item["multiplied"] == expected_original * 3