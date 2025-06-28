"""Python code execution node implementation with sandboxing"""

import asyncio
import json
import traceback
from functools import partial
from pathlib import Path
from typing import Any

from jinja2 import Template
from pydantic import ValidationError

from seriesoftubes.models import Node, PythonNodeConfig
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import PythonNodeInput, PythonNodeOutput
from seriesoftubes.secure_python import (
    PythonSecurityLevel,
    SecurePythonError,
    execute_secure_python,
)



def _parse_memory_limit(memory_str: str) -> int:
    """Parse memory limit string to bytes (in MB)"""
    memory_str = memory_str.upper().strip()
    multipliers = {"KB": 0.001, "MB": 1, "GB": 1024}

    for suffix, multiplier in multipliers.items():
        if memory_str.endswith(suffix):
            number = float(memory_str[: -len(suffix)])
            return int(number * multiplier)

    # Assume MB if no suffix
    return int(memory_str)


class PythonNodeExecutor(NodeExecutor):
    """Executor for Python code nodes with sandboxing"""

    input_schema_class = PythonNodeInput
    output_schema_class = PythonNodeOutput

    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute Python code with security restrictions"""
        # Type check
        if not isinstance(node.config, PythonNodeConfig):
            return NodeResult(
                output=None,
                success=False,
                error=f"Invalid config type for Python node: {type(node.config)}",
            )

        config = node.config

        try:
            # Prepare context data - don't unwrap Python results for Python nodes
            context_data = self.prepare_context_data(node, context, unwrap_python_results=False)

            # Always validate input when schema is defined
            input_data = {"context": context_data}

            try:
                validated_input = self.validate_input(input_data)
                context_data = validated_input["context"]
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

            # Get the code to execute
            if config.code:
                # Inline code
                code = config.code
            else:
                # File-based code
                file_path = config.file
                if not file_path:
                    msg = "File path is required when code is not provided"
                    raise ValueError(msg)

                # Render Jinja2 template in file path if needed
                if "{{" in file_path:
                    template = Template(file_path)
                    file_path = template.render(**context_data)

                # Read the file
                path = Path(file_path)
                if not path.exists():
                    msg = f"Python file not found: {file_path}"
                    raise FileNotFoundError(msg)

                code = path.read_text()

                # If a specific function is requested, wrap the call
                if config.function:
                    code = (
                        f"{code}\n\n"
                        f"# Call the specified function\n"
                        f"result = {config.function}()"
                    )

            # Determine security level based on configuration
            if hasattr(config, 'security_level'):
                security_level = PythonSecurityLevel(config.security_level)
            else:
                # Default to NORMAL for backward compatibility
                security_level = PythonSecurityLevel.NORMAL

            # Execute using secure Python engine
            try:
                # Use partial to properly pass keyword arguments
                execute_fn = partial(
                    execute_secure_python,
                    code,
                    context_data,
                    security_level,
                    timeout=config.timeout or 30,
                    memory_limit_mb=_parse_memory_limit(config.memory_limit) if config.memory_limit else 100,
                    allowed_imports=config.allowed_imports,
                )
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    execute_fn,
                )
            except SecurePythonError as e:
                return NodeResult(
                    output=None,
                    success=False,
                    error=f"Security error in Python node '{node.name}': {e}",
                )

            # Structure the output
            output = {"result": result}
            
            # Check output size limit
            if config.max_output_size:
                import json as json_module
                output_str = json_module.dumps(output)
                if len(output_str) > config.max_output_size:
                    return NodeResult(
                        output=None,
                        success=False,
                        error=f"Output size ({len(output_str)} bytes) exceeds limit ({config.max_output_size} bytes)",
                    )

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

            return NodeResult(output=output, success=True)

        except TimeoutError as e:
            return NodeResult(output=None, success=False, error=str(e))
        except (ValueError, FileNotFoundError) as e:
            return NodeResult(output=None, success=False, error=str(e))
        except Exception as e:
            # Capture full traceback for debugging
            tb = traceback.format_exc()
            return NodeResult(
                output=None,
                success=False,
                error=f"Python execution failed: {e!s}\n{tb}",
            )
