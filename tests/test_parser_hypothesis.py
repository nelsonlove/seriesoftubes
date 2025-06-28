from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from seriesoftubes.parser import parse_workflow_yaml, validate_dag

# Strategy for generating valid workflow structures
node_name_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=1,
    max_size=30,
)

node_type_strategy = st.sampled_from(["llm", "http", "python", "conditional", "file"])


def _generate_config_for_type(node_type: str) -> dict:
    """Generate a minimal valid config for each node type"""
    if node_type == "llm":
        return {"prompt": "Test prompt", "model": "gpt-3.5-turbo"}
    elif node_type == "http":
        return {"url": "https://httpbin.org/get", "method": "GET"}
    elif node_type == "python":
        return {"code": "return {'result': 42}"}
    elif node_type == "conditional":
        return {
            "conditions": [
                {"condition": "true", "then": "continue"}
            ]
        }
    elif node_type == "file":
        return {"path": "test.json", "operation": "read"}
    else:
        return {}


@st.composite
def workflow_dict_strategy(draw):
    """Generate valid workflow dictionaries"""
    num_nodes = draw(st.integers(min_value=1, max_value=10))
    node_names = draw(
        st.lists(
            node_name_strategy, min_size=num_nodes, max_size=num_nodes, unique=True
        )
    )

    nodes = {}
    for i, name in enumerate(node_names):
        # Create dependencies only to previous nodes (ensures no cycles)
        possible_deps = node_names[:i]
        deps = draw(
            st.lists(
                st.sampled_from(possible_deps) if possible_deps else st.nothing(),
                max_size=min(3, len(possible_deps)),
            )
        )

        node_type = draw(node_type_strategy)
        nodes[name] = {
            "type": node_type,
            "depends_on": deps,
            "config": _generate_config_for_type(node_type),
        }

    return {
        "name": draw(st.text(min_size=1, max_size=50)),
        "version": "1.0.0",
        "nodes": nodes,
    }


@given(workflow_dict=workflow_dict_strategy())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_valid_workflow_parsing(workflow_dict, tmp_path):
    """Any valid workflow dict should parse without errors"""
    import yaml

    workflow_file = tmp_path / "test_workflow.yaml"
    workflow_file.write_text(yaml.dump(workflow_dict))

    # Should parse without errors
    workflow = parse_workflow_yaml(workflow_file)

    # Should pass DAG validation (we ensured no cycles in generation)
    validate_dag(workflow)

    # Properties to verify:
    assert workflow.name == workflow_dict["name"]
    assert len(workflow.nodes) == len(workflow_dict["nodes"])

    # All dependencies should exist
    for node_name, node in workflow.nodes.items():
        for dep in node.depends_on:
            assert dep in workflow.nodes
