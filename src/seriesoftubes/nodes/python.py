"""Python code execution node implementation with sandboxing"""

import ast
import asyncio
import json
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from jinja2 import Template
from pydantic import ValidationError

from seriesoftubes.models import Node, PythonNodeConfig
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.schemas import PythonNodeInput, PythonNodeOutput

# Restricted builtins for sandboxed execution
ALLOWED_BUILTINS = {
    # Basic types and functions
    "len",
    "range",
    "enumerate",
    "zip",
    "map",
    "filter",
    "sum",
    "min",
    "max",
    "abs",
    "round",
    "sorted",
    "reversed",
    "any",
    "all",
    # Type constructors
    "dict",
    "list",
    "set",
    "tuple",
    "str",
    "int",
    "float",
    "bool",
    # Safe utilities
    "print",  # For debugging, output is captured
    "isinstance",
    "hasattr",
    "getattr",
    "setattr",
    "type",
    # JSON for serialization
    "json",
}


def _parse_memory_limit(memory_str: str) -> int:
    """Parse memory limit string to bytes"""
    memory_str = memory_str.upper().strip()
    multipliers = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}

    for suffix, multiplier in multipliers.items():
        if memory_str.endswith(suffix):
            number = float(memory_str[: -len(suffix)])
            return int(number * multiplier)

    # Assume bytes if no suffix
    return int(memory_str)


def _validate_code_safety(code: str) -> None:
    """Basic AST validation to catch obvious security issues"""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        msg = f"Invalid Python syntax: {e}"
        raise ValueError(msg) from e

    # Check for dangerous patterns
    for node in ast.walk(tree):
        # Prevent exec/eval
        if isinstance(node, ast.Name) and node.id in ("exec", "eval", "__import__"):
            msg = f"Use of '{node.id}' is not allowed"
            raise ValueError(msg)

        # Prevent attribute access on sensitive objects
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id in (
                "os",
                "sys",
                "subprocess",
            ):
                msg = f"Access to '{node.value.id}' module is not allowed"
                raise ValueError(msg)


def _execute_python_code(
    code: str, context: dict[str, Any], allowed_imports: list[str], max_output_size: int
) -> Any:
    """Execute Python code in a restricted environment"""
    # Create restricted globals
    import builtins  # noqa: PLC0415

    restricted_builtins = {}
    for name in ALLOWED_BUILTINS:
        if hasattr(builtins, name):
            restricted_builtins[name] = getattr(builtins, name)

    restricted_globals = {
        "__builtins__": restricted_builtins,
        "context": context,
        "json": json,  # Always allow json for serialization
    }

    # Pre-process code to handle imports
    processed_code = []
    import_lines = []

    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            # Extract module name
            if stripped.startswith("import "):
                module_name = stripped[7:].split()[0].split(".")[0]
            else:  # from X import Y
                module_name = stripped.split()[1].split(".")[0]

            if module_name not in allowed_imports:
                msg = f"Import of module '{module_name}' is not allowed"
                raise ValueError(msg)
            import_lines.append(line)
        else:
            processed_code.append(line)

    # Add allowed imports by pre-importing them
    for module_name in allowed_imports:
        try:
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                module = __import__(module_name)
            restricted_globals[module_name] = module
        except ImportError:
            msg = f"Cannot import module '{module_name}'"
            raise ValueError(msg) from None

    # Reconstruct code without import statements (since modules are pre-imported)
    code = "\n".join(processed_code)

    # Check if code contains 'return' statement outside function
    if "return " in code and "def " not in code:
        # Wrap the code in a function
        wrapped_code = "def _execute():\n"
        # Indent each line
        for line in code.splitlines():
            wrapped_code += f"    {line}\n"
        wrapped_code += "\nresult = _execute()"
        code = wrapped_code

    # Execute the code
    local_vars: dict[str, Any] = {}
    try:
        exec(code, restricted_globals, local_vars)  # noqa: S102
    except Exception as e:
        msg = f"Code execution failed: {e!s}"
        raise RuntimeError(msg) from e

    # Get the result
    if "result" in local_vars:
        result = local_vars["result"]
    elif "_execute" in local_vars and callable(local_vars["_execute"]):
        # Function was defined but not called
        result = local_vars["_execute"]()
    else:
        # Look for any non-underscore variable that was assigned
        for name, value in local_vars.items():
            if not name.startswith("_"):
                result = value
                break
        else:
            # No result found, return the modified context
            result = context

    # Validate output size
    output_json = json.dumps(result)
    if len(output_json) > max_output_size:
        msg = (
            f"Output size ({len(output_json)} bytes) "
            f"exceeds limit ({max_output_size} bytes)"
        )
        raise ValueError(msg)

    return result


async def _execute_in_process(
    code: str,
    context: dict[str, Any],
    allowed_imports: list[str],
    max_output_size: int,
    timeout: int,
) -> Any:
    """Execute code in a separate process with timeout"""
    loop = asyncio.get_event_loop()

    with ProcessPoolExecutor(max_workers=1) as executor:
        try:
            future = loop.run_in_executor(
                executor,
                _execute_python_code,
                code,
                context,
                allowed_imports,
                max_output_size,
            )
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except TimeoutError:
            msg = f"Code execution timed out after {timeout} seconds"
            raise TimeoutError(msg) from None
        except Exception:
            # Re-raise the exception from the subprocess
            raise


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
            # Prepare context data
            context_data = self.prepare_context_data(node, context)

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
                    error=f"Input validation failed for node '{node.name}':\n" + "\n".join(error_details),
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

            # Validate code safety
            _validate_code_safety(code)

            # Execute the code with restrictions
            result = await _execute_in_process(
                code,
                context_data,
                config.allowed_imports,
                config.max_output_size,
                config.timeout,
            )

            # Structure the output
            output = {"result": result}

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
                    error=f"Output validation failed for node '{node.name}':\n" + "\n".join(error_details),
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
