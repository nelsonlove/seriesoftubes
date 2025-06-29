"""Streaming Python code execution node implementation"""

import asyncio
import json
import traceback
from pathlib import Path
from typing import Any, AsyncIterator

from jinja2 import Template
from pydantic import ValidationError

from seriesoftubes.models import Node, PythonNodeConfig
from seriesoftubes.nodes.base import NodeContext, NodeExecutor, NodeResult
from seriesoftubes.nodes.python import PythonNodeExecutor, _parse_memory_limit
from seriesoftubes.schemas import PythonNodeInput, PythonNodeOutput
from seriesoftubes.secure_python import PythonSecurityLevel, SecurePythonError
from seriesoftubes.secure_python_streaming import (
    get_streaming_python_engine,
    StreamingSecurePythonEngine,
)


class StreamingPythonNodeExecutor(PythonNodeExecutor):
    """Executor for Python code nodes with streaming output support"""
    
    def __init__(self, stream_callback=None):
        """Initialize with optional stream callback.
        
        Args:
            stream_callback: Async callback(node_name, output_type, text) for streaming output
        """
        super().__init__()
        self.stream_callback = stream_callback
        self.streaming_engine = get_streaming_python_engine()
    
    async def execute_streaming(
        self, 
        node: Node, 
        context: NodeContext
    ) -> AsyncIterator[tuple[str, str]]:
        """Execute Python code with streaming output.
        
        Yields tuples of (output_type, text) where output_type is:
        - 'stdout': Standard output from the code
        - 'stderr': Error output from the code
        - 'progress': Progress updates
        - 'error': Execution errors
        - 'result': Final result (JSON-encoded)
        """
        # Type check
        if not isinstance(node.config, PythonNodeConfig):
            yield ('error', f"Invalid config type for Python node: {type(node.config)}")
            return
        
        config = node.config
        
        try:
            # Prepare context data
            context_data = self.prepare_context_data(node, context, unwrap_python_results=False)
            
            # Validate input
            input_data = {"context": context_data}
            try:
                validated_input = self.validate_input(input_data)
                context_data = validated_input["context"]
            except ValidationError as e:
                error_details = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error["loc"])
                    error_details.append(f"  - {field}: {error['msg']}")
                
                yield ('error', f"Input validation failed:\n" + "\n".join(error_details))
                return
            
            # Get the code to execute
            if config.code:
                code = config.code
            else:
                file_path = config.file
                if not file_path:
                    yield ('error', "File path is required when code is not provided")
                    return
                
                # Render Jinja2 template in file path if needed
                if "{{" in file_path:
                    template = Template(file_path)
                    file_path = template.render(**context_data)
                
                # Read the file
                path = Path(file_path)
                if not path.exists():
                    yield ('error', f"Python file not found: {file_path}")
                    return
                
                code = path.read_text()
                
                # If a specific function is requested, wrap the call
                if config.function:
                    code = (
                        f"{code}\n\n"
                        f"# Call the specified function\n"
                        f"result = {config.function}()"
                    )
            
            # Determine security level
            if hasattr(config, 'security_level'):
                security_level = PythonSecurityLevel(config.security_level)
            else:
                security_level = PythonSecurityLevel.NORMAL
            
            # Stream callback for real-time updates
            async def output_callback(output_type: str, text: str):
                if self.stream_callback:
                    await self.stream_callback(node.name, output_type, text)
            
            # Execute with streaming
            result = None
            timeout_seconds = config.timeout or 300  # Default to 5 minutes for streaming
            
            try:
                async for output_type, text, exec_result in self.streaming_engine.execute_streaming(
                    code=code,
                    context=context_data,
                    level=security_level,
                    timeout=timeout_seconds,
                    memory_limit_mb=_parse_memory_limit(config.memory_limit) if config.memory_limit else 100,
                    allowed_imports=config.allowed_imports,
                    output_callback=lambda ot, t: asyncio.create_task(output_callback(ot, t)),
                ):
                    if output_type == 'result':
                        result = exec_result
                    else:
                        yield (output_type, text)
                        
            except asyncio.TimeoutError:
                yield ('error', f"Python execution timed out after {timeout_seconds} seconds")
                return
            except SecurePythonError as e:
                error_msg = str(e)
                if "Syntax error" in error_msg and "'return' outside function" in error_msg:
                    error_msg = (
                        "Python node code executes at module level. "
                        "Use 'return <value>' to return a result. "
                        f"Original error: {error_msg}"
                    )
                yield ('error', f"Security error: {error_msg}")
                return
            
            # Structure and validate the output
            output = {"result": result}
            
            # Check output size limit
            if config.max_output_size:
                output_str = json.dumps(output)
                if len(output_str) > config.max_output_size:
                    yield ('error', f"Output size ({len(output_str)} bytes) exceeds limit ({config.max_output_size} bytes)")
                    return
            
            # Validate output
            try:
                output = self.validate_output(output)
                yield ('result', json.dumps(output))
            except ValidationError as e:
                error_details = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error["loc"])
                    error_details.append(f"  - {field}: {error['msg']}")
                
                yield ('error', f"Output validation failed:\n" + "\n".join(error_details))
                
        except Exception as e:
            tb = traceback.format_exc()
            yield ('error', f"Python execution failed: {str(e)}\n{tb}")
    
    async def execute(self, node: Node, context: NodeContext) -> NodeResult:
        """Execute Python code and collect all output.
        
        This method collects all streaming output and returns a standard NodeResult.
        """
        stdout_lines = []
        stderr_lines = []
        result = None
        error = None
        
        async for output_type, text in self.execute_streaming(node, context):
            if output_type == 'stdout':
                stdout_lines.append(text)
            elif output_type == 'stderr':
                stderr_lines.append(text)
            elif output_type == 'error':
                error = text
            elif output_type == 'result':
                result = json.loads(text)
            # Progress updates are ignored in non-streaming mode
        
        if error:
            # Include stdout/stderr in error message for debugging
            error_parts = [error]
            if stdout_lines:
                error_parts.append("\nStdout:\n" + "".join(stdout_lines))
            if stderr_lines:
                error_parts.append("\nStderr:\n" + "".join(stderr_lines))
            
            return NodeResult(
                output=None,
                success=False,
                error="\n".join(error_parts),
            )
        
        # Include stdout/stderr in metadata
        if result and (stdout_lines or stderr_lines):
            result['_stdout'] = "".join(stdout_lines)
            result['_stderr'] = "".join(stderr_lines)
        
        return NodeResult(output=result, success=True)