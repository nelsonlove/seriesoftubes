"""Streaming version of secure Python execution engine.

This module extends the secure Python execution engine to support
real-time streaming of stdout/stderr output during execution.
"""

import asyncio
import io
import sys
import threading
import time
from contextlib import redirect_stdout, redirect_stderr
from queue import Queue, Empty
from typing import Any, AsyncIterator, Callable

from seriesoftubes.secure_python import (
    SecurePythonEngine,
    PythonSecurityLevel,
    ExecutionError,
)


class StreamingOutput:
    """Captures and streams output from Python code execution"""
    
    def __init__(self, callback: Callable[[str, str], None] | None = None):
        """Initialize streaming output capture.
        
        Args:
            callback: Optional callback function(output_type, text) called for each output
        """
        self.stdout_buffer = io.StringIO()
        self.stderr_buffer = io.StringIO()
        self.output_queue = Queue()
        self.callback = callback
        self._stop_event = threading.Event()
        
    def write_stdout(self, text: str) -> None:
        """Write to stdout and queue for streaming"""
        self.stdout_buffer.write(text)
        self.output_queue.put(('stdout', text))
        if self.callback:
            self.callback('stdout', text)
            
    def write_stderr(self, text: str) -> None:
        """Write to stderr and queue for streaming"""
        self.stderr_buffer.write(text)
        self.output_queue.put(('stderr', text))
        if self.callback:
            self.callback('stderr', text)
            
    def get_output(self, timeout: float = 0.1) -> tuple[str, str] | None:
        """Get next output from queue"""
        try:
            return self.output_queue.get(timeout=timeout)
        except Empty:
            return None
            
    def stop(self) -> None:
        """Signal to stop streaming"""
        self._stop_event.set()
        
    def is_stopped(self) -> bool:
        """Check if streaming should stop"""
        return self._stop_event.is_set()


class StreamingStringIO(io.StringIO):
    """StringIO that streams output as it's written"""
    
    def __init__(self, streaming_output: StreamingOutput, output_type: str):
        super().__init__()
        self.streaming_output = streaming_output
        self.output_type = output_type
        
    def write(self, text: str) -> int:
        """Write text and stream it"""
        result = super().write(text)
        if self.output_type == 'stdout':
            self.streaming_output.write_stdout(text)
        else:
            self.streaming_output.write_stderr(text)
        return result


class StreamingSecurePythonEngine(SecurePythonEngine):
    """Secure Python engine with streaming output support"""
    
    async def execute_streaming(
        self,
        code: str,
        context: dict[str, Any] | None = None,
        level: PythonSecurityLevel | None = None,
        timeout: int = 30,
        memory_limit_mb: int = 100,
        allowed_imports: list[str] | None = None,
        output_callback: Callable[[str, str], None] | None = None,
    ) -> AsyncIterator[tuple[str, str, Any]]:
        """Execute Python code with streaming output.
        
        Yields tuples of (output_type, text, result) where:
        - output_type is 'stdout', 'stderr', 'progress', or 'result'
        - text is the output text (empty for 'result')
        - result is None except for final 'result' yield
        """
        streaming_output = StreamingOutput(output_callback)
        
        # Create execution thread
        result_container = {'result': None, 'error': None, 'completed': False}
        
        def execute_in_thread():
            """Execute code in separate thread to allow streaming"""
            stdout_stream = StreamingStringIO(streaming_output, 'stdout')
            stderr_stream = StreamingStringIO(streaming_output, 'stderr')
            
            try:
                # Redirect stdout/stderr to our streams
                with redirect_stdout(stdout_stream), redirect_stderr(stderr_stream):
                    # Override print in the execution context
                    if context is None:
                        context = {}
                    
                    # Create custom print that writes to our stdout
                    def streaming_print(*args, **kwargs):
                        output = io.StringIO()
                        print(*args, file=output, **kwargs)
                        text = output.getvalue()
                        stdout_stream.write(text)
                    
                    context['print'] = streaming_print
                    
                    # Execute the code
                    result = self.execute(
                        code=code,
                        context=context,
                        level=level,
                        timeout=timeout,
                        memory_limit_mb=memory_limit_mb,
                        allowed_imports=allowed_imports,
                    )
                    
                    result_container['result'] = result
                    
            except Exception as e:
                result_container['error'] = e
                stderr_stream.write(f"\nExecution error: {e}\n")
            finally:
                result_container['completed'] = True
                streaming_output.stop()
        
        # Start execution thread
        exec_thread = threading.Thread(target=execute_in_thread, daemon=True)
        exec_thread.start()
        
        # Stream output while execution is running
        start_time = time.time()
        last_progress_time = start_time
        
        while not result_container['completed'] or not streaming_output.output_queue.empty():
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout and not result_container['completed']:
                streaming_output.stop()
                yield ('stderr', f"\nExecution timed out after {timeout} seconds\n", None)
                raise ExecutionError(f"Execution timed out after {timeout} seconds")
            
            # Get output from queue
            output = streaming_output.get_output(timeout=0.1)
            if output:
                output_type, text = output
                yield (output_type, text, None)
            
            # Send progress updates every 5 seconds
            if time.time() - last_progress_time > 5:
                last_progress_time = time.time()
                elapsed_mins = int(elapsed / 60)
                elapsed_secs = int(elapsed % 60)
                yield ('progress', f"Execution time: {elapsed_mins}m {elapsed_secs}s", None)
            
            # Small sleep to prevent busy waiting
            await asyncio.sleep(0.01)
        
        # Wait for thread to complete
        exec_thread.join(timeout=1)
        
        # Return final result or raise error
        if result_container['error']:
            raise result_container['error']
        else:
            yield ('result', '', result_container['result'])
    
    def execute_with_output_capture(
        self,
        code: str,
        context: dict[str, Any] | None = None,
        level: PythonSecurityLevel | None = None,
        timeout: int = 30,
        memory_limit_mb: int = 100,
        allowed_imports: list[str] | None = None,
    ) -> tuple[Any, str, str]:
        """Execute code and capture stdout/stderr.
        
        Returns:
            Tuple of (result, stdout, stderr)
        """
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            # Override print in the execution context
            if context is None:
                context = {}
            
            # Create custom print that writes to our stdout
            def captured_print(*args, **kwargs):
                print(*args, **kwargs)
            
            context['print'] = captured_print
            
            try:
                result = self.execute(
                    code=code,
                    context=context,
                    level=level,
                    timeout=timeout,
                    memory_limit_mb=memory_limit_mb,
                    allowed_imports=allowed_imports,
                )
                
                return result, stdout_capture.getvalue(), stderr_capture.getvalue()
                
            except Exception as e:
                # Include error in stderr
                stderr_capture.write(f"\nExecution error: {e}\n")
                return None, stdout_capture.getvalue(), stderr_capture.getvalue()


# Global streaming engine instance
_streaming_engine = None


def get_streaming_python_engine() -> StreamingSecurePythonEngine:
    """Get the global streaming Python engine instance"""
    global _streaming_engine
    if _streaming_engine is None:
        _streaming_engine = StreamingSecurePythonEngine()
    return _streaming_engine


async def execute_python_streaming(
    code: str,
    context: dict[str, Any] | None = None,
    level: PythonSecurityLevel | None = None,
    output_callback: Callable[[str, str], None] | None = None,
    **kwargs
) -> AsyncIterator[tuple[str, str, Any]]:
    """Convenience function to execute Python code with streaming output"""
    engine = get_streaming_python_engine()
    async for output in engine.execute_streaming(
        code, context, level, output_callback=output_callback, **kwargs
    ):
        yield output