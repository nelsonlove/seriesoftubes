"""File ingestion node executor implementation"""

import csv
import glob
import json
import random
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Template
from pydantic import ValidationError

from seriesoftubes.models import FileNodeConfig, Node
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import FileNodeInput, FileNodeOutput

# Optional imports for document processing
try:
    import PyPDF2

    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from docx import Document

    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import openpyxl

    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False

try:
    from bs4 import BeautifulSoup

    HAS_HTML = True
except ImportError:
    HAS_HTML = False


class FileNodeExecutor(NodeExecutor):
    """Executor for file ingestion nodes"""

    input_schema_class = FileNodeInput
    output_schema_class = FileNodeOutput

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute a file ingestion node"""
        if not isinstance(node.config, FileNodeConfig):
            return NodeResult(
                output=None,
                success=False,
                error=f"Invalid config type for file node: {type(node.config)}",
            )

        config = node.config

        try:
            # Prepare context for template rendering
            context_data = self.prepare_context_data(node, context)

            # Always validate input when schema is defined
            # Extract the rendered path/pattern for validation
            rendered_path = None
            rendered_pattern = None

            if config.path:
                rendered_path = self._render_template(config.path, context_data)
            elif config.pattern:
                rendered_pattern = self._render_template(config.pattern, context_data)

            input_data = {
                "path": rendered_path,
                "pattern": rendered_pattern,
            }

            try:
                validated_input = self.validate_input(input_data)
                # Update config with validated values
                if validated_input.get("path"):
                    config.path = validated_input["path"]
                if validated_input.get("pattern"):
                    config.pattern = validated_input["pattern"]
            except ValidationError as e:
                # Format validation errors for clarity
                error_details = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error["loc"])
                    error_details.append(f"  - {field}: {error['msg']}")

                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Input validation failed for node '{node.name}':\n"
                    + "\n".join(error_details),
                )

            # Get file paths
            paths = self._get_file_paths(config, context_data)

            if not paths:
                return NodeResult(
                    output=None,
                    success=False,
                    error="No files found matching criteria",
                )

            # Process based on number of files and output mode
            if len(paths) == 1:
                # Single file
                data = await self._process_single_file(paths[0], config)
            else:
                # Multiple files
                data = await self._process_multiple_files(paths, config)

            # Structure the output
            output = {
                "data": data,
                "metadata": {
                    "files_read": len(paths),
                    "output_mode": config.output_mode,
                    "format": config.format_type,
                },
            }

            # Always validate output when schema is defined
            try:
                output = self.validate_output(output)
            except ValidationError as e:
                # Format validation errors for clarity
                error_details = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error["loc"])
                    error_details.append(f"  - {field}: {error['msg']}")

                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Output validation failed for node '{node.name}':\n"
                    + "\n".join(error_details),
                )

            return NodeResult(
                output=output,
                success=True,
                metadata={
                    "files_read": len(paths),
                    "output_mode": config.output_mode,
                },
            )

        except Exception as e:
            return NodeResult(
                output=None,
                success=False,
                error=str(e),
            )

    def _get_file_paths(
        self, config: FileNodeConfig, context: dict[str, Any]
    ) -> list[Path]:
        """Get list of file paths based on config"""
        paths = []

        if config.path:
            # Single file path
            rendered_path = self._render_template(config.path, context)
            path = Path(rendered_path)
            if path.exists():
                paths.append(path)
            elif not config.skip_errors:
                msg = f"File not found: {path}"
                raise FileNotFoundError(msg)

        elif config.pattern:
            # Glob pattern
            rendered_pattern = self._render_template(config.pattern, context)
            # Handle recursive globs
            if "**" in rendered_pattern:
                found_paths = list(Path(".").glob(rendered_pattern))
            else:
                found_paths = [Path(p) for p in glob.glob(rendered_pattern)]

            for p in found_paths:
                path = Path(p)
                if path.is_file():
                    paths.append(path)

        return sorted(paths)  # Consistent ordering

    async def _process_single_file(self, path: Path, config: FileNodeConfig) -> Any:
        """Process a single file"""
        content = await self._read_file(path, config)

        # Apply transformations
        if config.format_type in ["csv", "jsonl"] and isinstance(content, list):
            content = self._apply_filters(content, config)

        # Return based on output mode
        if config.output_mode == "list" and not isinstance(content, list):
            return [content]
        return content

    async def _process_multiple_files(
        self, paths: list[Path], config: FileNodeConfig
    ) -> Any:
        """Process multiple files"""
        if config.merge:
            # Merge files into single output
            merged = []
            for path in paths:
                try:
                    content = await self._read_file(path, config)
                    if isinstance(content, list):
                        merged.extend(content)
                    else:
                        merged.append(content)
                except Exception:
                    if not config.skip_errors:
                        raise
                    # Skip this file

            # Apply filters to merged content
            if config.format_type in ["csv", "jsonl"]:
                merged = self._apply_filters(merged, config)

            return merged

        else:
            # Keep files separate
            output = {}
            for path in paths:
                try:
                    content = await self._read_file(path, config)
                    # Apply filters per file
                    if config.format_type in ["csv", "jsonl"] and isinstance(
                        content, list
                    ):
                        content = self._apply_filters(content, config)
                    output[str(path)] = content
                except Exception as e:
                    if not config.skip_errors:
                        raise
                    output[str(path)] = {"error": str(e)}

            # Return based on output mode
            if config.output_mode == "list":
                return list(output.values())
            return output

    async def _read_file(self, path: Path, config: FileNodeConfig) -> Any:
        """Read a single file based on format"""
        # Auto-detect format from extension
        file_format = config.format_type
        if file_format == "auto":
            suffix = path.suffix.lower()
            if suffix in [".json"]:
                file_format = "json"
            elif suffix in [".jsonl", ".ndjson"]:
                file_format = "jsonl"
            elif suffix in [".yaml", ".yml"]:
                file_format = "yaml"
            elif suffix in [".csv"]:
                file_format = "csv"
            elif suffix in [".pdf"]:
                file_format = "pdf"
            elif suffix in [".docx"]:
                file_format = "docx"
            elif suffix in [".xlsx", ".xls"]:
                file_format = "xlsx"
            elif suffix in [".html", ".htm"]:
                file_format = "html"
            else:
                file_format = "txt"

        # Read based on format
        if file_format == "json":
            with open(path, encoding=config.encoding) as f:
                return json.load(f)
        elif file_format == "jsonl":
            return self._read_jsonl(path, config)
        elif file_format == "yaml":
            with open(path, encoding=config.encoding) as f:
                return yaml.safe_load(f)
        elif file_format == "csv":
            return self._read_csv(path, config)
        elif file_format == "pdf":
            return self._read_pdf(path, config)
        elif file_format == "docx":
            return self._read_docx(path, config)
        elif file_format == "xlsx":
            return self._read_xlsx(path, config)
        elif file_format == "html":
            return self._read_html(path, config)
        else:
            # Default to text
            with open(path, encoding=config.encoding) as f:
                return f.read()

    def _read_jsonl(self, path: Path, config: FileNodeConfig) -> list[dict[str, Any]]:
        """Read JSONL file"""
        rows = []
        with open(path, encoding=config.encoding) as f:
            for line_num, line in enumerate(f):
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        if not config.skip_errors:
                            msg = f"Invalid JSON on line {line_num + 1}: {e}"
                            raise ValueError(msg) from e
        return rows

    def _read_csv(self, path: Path, config: FileNodeConfig) -> list[dict[str, Any]]:
        """Read CSV file into list of dicts"""
        rows = []
        with open(path, encoding=config.encoding) as f:
            if config.has_header:
                dict_reader = csv.DictReader(f, delimiter=config.delimiter)
                for row in dict_reader:
                    rows.append(dict(row))
            else:
                list_reader = csv.reader(f, delimiter=config.delimiter)
                for row in list_reader:  # type: ignore[assignment]
                    rows.append({f"col_{j}": val for j, val in enumerate(row)})
        return rows

    def _apply_filters(self, records: list[Any], config: FileNodeConfig) -> list[Any]:
        """Apply sampling, limiting, etc. to records"""
        # Sample
        if config.sample is not None and 0 < config.sample < 1:
            num_samples = int(len(records) * config.sample)
            records = random.sample(records, num_samples)

        # Limit
        if config.limit is not None and config.limit > 0:
            records = records[: config.limit]

        return records

    def _read_pdf(self, path: Path, config: FileNodeConfig) -> Any:
        """Read PDF file"""
        if not HAS_PDF:
            msg = "PDF support requires PyPDF2. Install with: pip install PyPDF2"
            raise ImportError(msg)

        if config.extract_text:
            # Extract text from PDF
            text = []
            with open(path, "rb") as f:
                pdf_reader = PyPDF2.PdfFileReader(f)
                for page_num in range(pdf_reader.numPages):
                    page = pdf_reader.getPage(page_num)
                    text.append(page.extractText())
            return "\n".join(text)
        else:
            # Return metadata only
            with open(path, "rb") as f:
                pdf_reader = PyPDF2.PdfFileReader(f)
                return {
                    "num_pages": pdf_reader.numPages,
                    "metadata": pdf_reader.getDocumentInfo(),
                    "path": str(path),
                }

    def _read_docx(self, path: Path, config: FileNodeConfig) -> Any:
        """Read DOCX file"""
        if not HAS_DOCX:
            msg = (
                "DOCX support requires python-docx. Install with: "
                "pip install python-docx"
            )
            raise ImportError(msg)

        doc = Document(path)

        if config.extract_text:
            # Extract text from document
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        else:
            # Return structured content
            return {
                "paragraphs": [p.text for p in doc.paragraphs],
                "tables": [
                    [[cell.text for cell in row.cells] for row in table.rows]
                    for table in doc.tables
                ],
                "path": str(path),
            }

    def _read_xlsx(self, path: Path, config: FileNodeConfig) -> Any:
        """Read Excel file"""
        if not HAS_XLSX:
            msg = "Excel support requires openpyxl. Install with: pip install openpyxl"
            raise ImportError(msg)

        workbook = openpyxl.load_workbook(path, data_only=True)

        # For now, just read the first sheet as CSV-like data
        sheet = workbook.active
        if sheet is None:
            return []
        rows = []

        # Get all rows
        all_rows = list(sheet.iter_rows(values_only=True))

        if all_rows and config.has_header:
            # Use first row as headers
            headers = [str(h) if h else f"col_{i}" for i, h in enumerate(all_rows[0])]
            for row in all_rows[1:]:
                row_dict = {}
                for i, value in enumerate(row):
                    if i < len(headers):
                        row_dict[headers[i]] = value
                if any(row_dict.values()):  # Skip empty rows
                    rows.append(row_dict)
        else:
            # No headers
            for row in all_rows:
                row_dict = {f"col_{i}": value for i, value in enumerate(row)}
                if any(row_dict.values()):  # Skip empty rows
                    rows.append(row_dict)

        return rows

    def _read_html(self, path: Path, config: FileNodeConfig) -> Any:
        """Read HTML file"""
        if not HAS_HTML:
            msg = (
                "HTML support requires beautifulsoup4. Install with: "
                "pip install beautifulsoup4"
            )
            raise ImportError(msg)

        with open(path, encoding=config.encoding) as f:
            soup = BeautifulSoup(f, "html.parser")

        if config.extract_text:
            # Extract visible text
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Break into lines and remove empty ones
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            return text
        else:
            # Return structured content
            return {
                "title": soup.title.string if soup.title else None,
                "text": soup.get_text(),
                "links": [
                    {"href": a.get("href"), "text": a.get_text()}
                    for a in soup.find_all("a")
                ],
                "path": str(path),
            }

    def _render_template(self, template_str: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 template string"""
        template = Template(template_str)
        return template.render(**context)
