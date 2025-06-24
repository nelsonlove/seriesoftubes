"""Tests for file node executor"""

import json

import pytest
import yaml

from seriesoftubes.models import FileNodeConfig, Node, NodeType
from seriesoftubes.nodes import FileNodeExecutor


class MockContext:
    """Mock implementation of NodeContext protocol"""

    def __init__(self, outputs=None, inputs=None):
        self.outputs = outputs or {}
        self.inputs = inputs or {}

    def get_output(self, node_name: str):
        return self.outputs.get(node_name)

    def get_input(self, input_name: str):
        return self.inputs.get(input_name)


@pytest.fixture
def temp_files(tmp_path):
    """Create temporary test files"""
    # JSON file
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps({"key": "value", "number": 42}))

    # CSV file
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\n")

    # YAML file
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml.dump({"config": {"enabled": True}}))

    # Text file
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Hello, world!")

    # JSONL file
    jsonl_file = tmp_path / "test.jsonl"
    jsonl_file.write_text('{"id": 1, "name": "Alice"}\n{"id": 2, "name": "Bob"}\n')

    return {
        "json": json_file,
        "csv": csv_file,
        "yaml": yaml_file,
        "txt": txt_file,
        "jsonl": jsonl_file,
        "dir": tmp_path,
    }


class TestFileNodeExecutor:
    """Test FileNodeExecutor"""

    @pytest.mark.asyncio
    async def test_read_json_file(self, temp_files):
        """Test reading a JSON file"""
        executor = FileNodeExecutor()
        node = Node(
            name="load_json",
            type=NodeType.FILE,
            config=FileNodeConfig(path=str(temp_files["json"])),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert result.success
        assert result.output == {"key": "value", "number": 42}
        assert result.metadata["files_read"] == 1

    @pytest.mark.asyncio
    async def test_read_csv_file(self, temp_files):
        """Test reading a CSV file"""
        executor = FileNodeExecutor()
        node = Node(
            name="load_csv",
            type=NodeType.FILE,
            config=FileNodeConfig(path=str(temp_files["csv"]), format="csv"),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert result.success
        assert isinstance(result.output, list)
        assert len(result.output) == 2
        assert result.output[0] == {"name": "Alice", "age": "30", "city": "NYC"}

    @pytest.mark.asyncio
    async def test_read_yaml_file(self, temp_files):
        """Test reading a YAML file"""
        executor = FileNodeExecutor()
        node = Node(
            name="load_yaml",
            type=NodeType.FILE,
            config=FileNodeConfig(path=str(temp_files["yaml"])),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert result.success
        assert result.output == {"config": {"enabled": True}}

    @pytest.mark.asyncio
    async def test_read_text_file(self, temp_files):
        """Test reading a text file"""
        executor = FileNodeExecutor()
        node = Node(
            name="load_txt",
            type=NodeType.FILE,
            config=FileNodeConfig(path=str(temp_files["txt"])),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert result.success
        assert result.output == "Hello, world!"

    @pytest.mark.asyncio
    async def test_read_jsonl_file(self, temp_files):
        """Test reading a JSONL file"""
        executor = FileNodeExecutor()
        node = Node(
            name="load_jsonl",
            type=NodeType.FILE,
            config=FileNodeConfig(path=str(temp_files["jsonl"])),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert result.success
        assert isinstance(result.output, list)
        assert len(result.output) == 2
        assert result.output[0] == {"id": 1, "name": "Alice"}

    @pytest.mark.asyncio
    async def test_glob_pattern(self, temp_files):
        """Test reading multiple files with glob pattern"""
        executor = FileNodeExecutor()
        node = Node(
            name="load_multiple",
            type=NodeType.FILE,
            config=FileNodeConfig(pattern=str(temp_files["dir"] / "*.json")),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert result.success
        # With single file match, returns content directly
        assert result.output == {"key": "value", "number": 42}

    @pytest.mark.asyncio
    async def test_merge_multiple_files(self, temp_files):
        """Test merging multiple CSV files"""
        # Create additional CSV file
        csv2 = temp_files["dir"] / "test2.csv"
        csv2.write_text("name,age,city\nCharlie,35,SF\n")

        executor = FileNodeExecutor()
        node = Node(
            name="merge_csv",
            type=NodeType.FILE,
            config=FileNodeConfig(
                pattern=str(temp_files["dir"] / "*.csv"),
                merge=True,
            ),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert result.success
        assert isinstance(result.output, list)
        assert len(result.output) == 3  # 2 from first file + 1 from second

    @pytest.mark.asyncio
    async def test_sample_and_limit(self, temp_files):
        """Test sampling and limiting records"""
        executor = FileNodeExecutor()
        node = Node(
            name="sample_csv",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(temp_files["csv"]),
                format="csv",  # Need to specify format for filters to apply
                limit=1,
            ),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert result.success
        assert isinstance(result.output, list)
        assert len(result.output) == 1

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        """Test handling of missing file"""
        executor = FileNodeExecutor()
        node = Node(
            name="missing_file",
            type=NodeType.FILE,
            config=FileNodeConfig(path="/nonexistent/file.json"),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert not result.success
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_skip_errors(self):
        """Test skip_errors option"""
        executor = FileNodeExecutor()
        node = Node(
            name="skip_errors",
            type=NodeType.FILE,
            config=FileNodeConfig(
                pattern="/nonexistent/*.json",
                skip_errors=True,
            ),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert not result.success  # No files found
        assert "No files found" in result.error

    @pytest.mark.asyncio
    async def test_template_rendering(self, temp_files):
        """Test Jinja2 template rendering in paths"""
        executor = FileNodeExecutor()
        node = Node(
            name="template_path",
            type=NodeType.FILE,
            config=FileNodeConfig(path="{{ inputs.filepath }}"),
        )

        context = MockContext(inputs={"filepath": str(temp_files["json"])})
        result = await executor.execute(node, context)

        assert result.success
        assert result.output == {"key": "value", "number": 42}

    @pytest.mark.asyncio
    async def test_csv_without_header(self, temp_files):
        """Test reading CSV without header"""
        csv_no_header = temp_files["dir"] / "no_header.csv"
        csv_no_header.write_text("Alice,30,NYC\nBob,25,LA\n")

        executor = FileNodeExecutor()
        node = Node(
            name="csv_no_header",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(csv_no_header),
                has_header=False,
            ),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert result.success
        assert isinstance(result.output, list)
        assert result.output[0] == {"col_0": "Alice", "col_1": "30", "col_2": "NYC"}

    @pytest.mark.asyncio
    async def test_output_modes(self, temp_files):
        """Test different output modes"""
        executor = FileNodeExecutor()

        # List mode for single file
        node = Node(
            name="list_mode",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(temp_files["json"]),
                output_mode="list",
            ),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert result.success
        assert isinstance(result.output, list)
        assert result.output == [{"key": "value", "number": 42}]

    @pytest.mark.asyncio
    async def test_auto_format_detection(self, temp_files):
        """Test automatic format detection"""
        executor = FileNodeExecutor()

        # Should auto-detect JSON
        node = Node(
            name="auto_json",
            type=NodeType.FILE,
            config=FileNodeConfig(
                path=str(temp_files["json"]),
                format="auto",  # Default
            ),
        )

        context = MockContext()
        result = await executor.execute(node, context)

        assert result.success
        assert isinstance(result.output, dict)
