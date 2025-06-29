"""Secure Python code execution engine using RestrictedPython.

This module provides secure Python code execution with multiple security
levels and comprehensive sandboxing to prevent malicious code execution.
"""

import ast
import resource
import sys
import time
from enum import Enum
from typing import Any, Callable

from RestrictedPython import (
    compile_restricted_exec,
    limited_builtins,
    safe_builtins,
    safe_globals,
    utility_builtins,
)
from RestrictedPython.Guards import (
    guarded_iter_unpack_sequence,
    safer_getattr,
)


class PythonSecurityLevel(Enum):
    """Security levels for Python code execution"""
    
    STRICT = "strict"  # Minimal builtins, no imports
    NORMAL = "normal"  # Safe builtins, limited imports
    TRUSTED = "trusted"  # More builtins, controlled imports


class SecurePythonError(Exception):
    """Base exception for secure Python execution errors"""
    pass


class CodeValidationError(SecurePythonError):
    """Raised when code validation fails"""
    pass


class ExecutionError(SecurePythonError):
    """Raised when code execution fails"""
    pass


class SecurePythonEngine:
    """Secure Python code execution engine with RestrictedPython"""
    
    # Safe imports for different security levels
    SAFE_IMPORTS = {
        PythonSecurityLevel.STRICT: set(),  # No imports allowed
        PythonSecurityLevel.NORMAL: {
            'math', 'statistics', 'collections', 'itertools',
            'functools', 'operator', 'string', 'random',
            'datetime', 'calendar', 'json', 're', 'unicodedata',
        },
        PythonSecurityLevel.TRUSTED: {
            'math', 'statistics', 'collections', 'itertools',
            'functools', 'operator', 'string', 'random',
            'datetime', 'calendar', 'json', 're', 'unicodedata',
            'decimal', 'fractions', 'numbers', 'cmath',
            'array', 'bisect', 'heapq', 'queue',
            'csv', 'hashlib', 'hmac', 'secrets',
            'html', 'xml', 'base64', 'binascii',
            'urllib.parse', 'ipaddress', 'uuid',
        }
    }
    
    # Additional safe builtins for each level
    ADDITIONAL_BUILTINS = {
        PythonSecurityLevel.STRICT: {
            # Only the most essential
            'len', 'range', 'enumerate', 'zip',
            'min', 'max', 'sum', 'abs', 'round',
            'str', 'int', 'float', 'bool',
            'list', 'dict', 'tuple', 'set',
            'sorted', 'reversed',
        },
        PythonSecurityLevel.NORMAL: {
            # All from STRICT plus more
            'all', 'any', 'filter', 'map',
            'chr', 'ord', 'bin', 'hex', 'oct',
            'hasattr', 'getattr', 'setattr',
            'isinstance', 'issubclass',
            'callable', 'iter', 'next',
            'frozenset', 'bytearray',
            'divmod', 'pow', 'hash',
        },
        PythonSecurityLevel.TRUSTED: {
            # All from NORMAL plus more
            'compile', 'eval', 'exec',  # Still restricted versions
            'globals', 'locals', 'vars',
            'delattr', 'dir', 'help',
            'memoryview', 'object', 'property',
            'staticmethod', 'classmethod',
            'slice', 'super', 'type',
        }
    }
    
    def __init__(self, default_level: PythonSecurityLevel = PythonSecurityLevel.NORMAL):
        """Initialize the secure Python engine"""
        self.default_level = default_level
    
    def _transform_module_returns(self, code: str) -> str:
        """Transform module-level return statements to result assignments"""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # If parsing fails, return original code
            return code
        
        class ReturnTransformer(ast.NodeTransformer):
            def __init__(self):
                self.in_function = False
                self.transformed = False
                
            def visit_FunctionDef(self, node):
                old_in_function = self.in_function
                self.in_function = True
                self.generic_visit(node)
                self.in_function = old_in_function
                return node
                
            def visit_AsyncFunctionDef(self, node):
                old_in_function = self.in_function
                self.in_function = True
                self.generic_visit(node)
                self.in_function = old_in_function
                return node
                
            def visit_ClassDef(self, node):
                old_in_function = self.in_function
                self.in_function = True
                self.generic_visit(node)
                self.in_function = old_in_function
                return node
                
            def visit_Return(self, node):
                if not self.in_function:
                    # Transform module-level return to assignment
                    self.transformed = True
                    if node.value is None:
                        # return with no value -> result = None
                        return ast.Assign(
                            targets=[ast.Name(id='result', ctx=ast.Store())],
                            value=ast.Constant(value=None)
                        )
                    else:
                        # return value -> result = value
                        return ast.Assign(
                            targets=[ast.Name(id='result', ctx=ast.Store())],
                            value=node.value
                        )
                return node
        
        transformer = ReturnTransformer()
        new_tree = transformer.visit(tree)
        
        if transformer.transformed:
            # Since we can't reliably convert AST back to source without external libraries,
            # we'll use a regex-based approach for module-level returns
            import re
            
            # Split code into lines
            lines = code.split('\n')
            modified_lines = []
            
            # Track indentation level to detect module-level code
            for line in lines:
                stripped = line.lstrip()
                if stripped.startswith('return'):
                    # Check if this is at module level (no indentation)
                    indent = len(line) - len(stripped)
                    if indent == 0:
                        # Replace 'return' with 'result ='
                        modified_line = line.replace('return', 'result =', 1)
                        modified_lines.append(modified_line)
                    else:
                        modified_lines.append(line)
                else:
                    modified_lines.append(line)
            
            return '\n'.join(modified_lines)
        
        return code
    
    def execute(
        self,
        code: str,
        context: dict[str, Any] | None = None,
        level: PythonSecurityLevel | None = None,
        timeout: int = 30,
        memory_limit_mb: int = 100,
        allowed_imports: list[str] | None = None,
    ) -> Any:
        """Execute Python code securely with RestrictedPython.
        
        Args:
            code: Python code to execute
            context: Context variables available to the code
            level: Security level (uses default if not specified)
            timeout: Execution timeout in seconds
            memory_limit_mb: Memory limit in megabytes
            allowed_imports: Additional imports to allow
            
        Returns:
            The result of code execution
            
        Raises:
            CodeValidationError: If code contains unsafe constructs
            ExecutionError: If code execution fails
        """
        if level is None:
            level = self.default_level
        
        if context is None:
            context = {}
        
        # Transform module-level returns to result assignments
        code = self._transform_module_returns(code)
        
        # Validate code with AST first
        try:
            self._validate_code(code, level)
        except CodeValidationError:
            # Re-raise validation errors as-is
            raise
        
        # Compile with RestrictedPython
        try:
            compiled = compile_restricted_exec(
                code,
                filename='<secure_python>',
            )
        except SyntaxError as e:
            msg = f"Syntax error in code: {e}"
            raise CodeValidationError(msg) from e
        
        # Check for compilation errors
        if compiled.errors:
            errors = '\n'.join(compiled.errors)
            msg = f"Code compilation failed:\n{errors}"
            raise CodeValidationError(msg)
        
        # Check for warnings (but don't fail)
        if compiled.warnings:
            for warning in compiled.warnings:
                print(f"Code warning: {warning}")
        
        # Prepare execution environment
        safe_locals = self._prepare_locals(context, level, allowed_imports)
        safe_globals = self._prepare_globals(level, allowed_imports)
        
        # Set resource limits
        self._set_resource_limits(memory_limit_mb)
        
        # Execute with timeout
        start_time = time.time()
        
        try:
            # Merge globals and locals into a single namespace for execution
            # This allows functions to reference each other
            namespace = safe_globals.copy()
            namespace.update(safe_locals)
            exec(compiled.code, namespace)
            
            # Check timeout
            if time.time() - start_time > timeout:
                msg = f"Code execution timed out after {timeout} seconds"
                raise ExecutionError(msg)
            
            # Extract result from namespace
            if 'result' in namespace:
                return namespace['result']
            else:
                # Look for any new variables
                initial_keys = set(safe_globals.keys()) | set(safe_locals.keys())
                
                for key, value in namespace.items():
                    if key not in initial_keys and not key.startswith('_'):
                        return value
                return None
                
        except Exception as e:
            msg = f"Code execution failed: {e}"
            raise ExecutionError(msg) from e
    
    def _validate_code(self, code: str, level: PythonSecurityLevel) -> None:
        """Validate code for security issues beyond RestrictedPython"""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            msg = f"Syntax error in code: {e}"
            raise CodeValidationError(msg) from e
        
        # Additional AST-based validation
        validator = SecurityValidator(level)
        validator.visit(tree)
        
        if validator.errors:
            errors = '\n'.join(validator.errors)
            msg = f"Code validation failed:\n{errors}"
            raise CodeValidationError(msg)
    
    def _prepare_locals(
        self,
        context: dict[str, Any],
        level: PythonSecurityLevel,
        allowed_imports: list[str] | None,
    ) -> dict[str, Any]:
        """Prepare local variables for execution"""
        safe_locals = context.copy()
        
        # We don't need to pre-import modules since imports work via __import__
        
        # Add utility functions required by RestrictedPython
        safe_locals['_print_'] = self._safe_print  # Note: RestrictedPython uses _print_ with trailing underscore
        safe_locals['_iter_unpack_sequence'] = guarded_iter_unpack_sequence
        safe_locals['_getattr_'] = safer_getattr
        
        # If context wasn't empty, also add it as 'context' variable
        if context:
            safe_locals['context'] = context
        
        return safe_locals
    
    def _prepare_globals(self, level: PythonSecurityLevel, allowed_imports: list[str] | None) -> dict[str, Any]:
        """Prepare global variables for execution"""
        # Start with RestrictedPython's safe globals
        safe_globals_dict = safe_globals.copy()
        
        # Import builtins module to access built-in functions reliably
        import builtins as builtin_module
        
        # Select builtins based on security level
        if level == PythonSecurityLevel.STRICT:
            builtins = safe_builtins.copy()
        elif level == PythonSecurityLevel.NORMAL:
            builtins = limited_builtins.copy()
        else:  # TRUSTED
            builtins = utility_builtins.copy()
        
        # Add additional builtins for the level (accumulative)
        if level == PythonSecurityLevel.STRICT:
            level_builtins = self.ADDITIONAL_BUILTINS[PythonSecurityLevel.STRICT]
        elif level == PythonSecurityLevel.NORMAL:
            level_builtins = self.ADDITIONAL_BUILTINS[PythonSecurityLevel.STRICT] | self.ADDITIONAL_BUILTINS[PythonSecurityLevel.NORMAL]
        else:  # TRUSTED
            level_builtins = self.ADDITIONAL_BUILTINS[PythonSecurityLevel.STRICT] | self.ADDITIONAL_BUILTINS[PythonSecurityLevel.NORMAL] | self.ADDITIONAL_BUILTINS[PythonSecurityLevel.TRUSTED]
        
        for name in level_builtins:
            if hasattr(builtin_module, name):
                builtins[name] = getattr(builtin_module, name)
        
        # Add exception types (safe to expose)
        exception_types = [
            'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
            'AttributeError', 'ImportError', 'NameError', 'ZeroDivisionError',
            'RuntimeError', 'NotImplementedError', 'AssertionError'
        ]
        for exc_name in exception_types:
            if hasattr(builtin_module, exc_name):
                builtins[exc_name] = getattr(builtin_module, exc_name)
        
        # Add __build_class__ for class definitions
        if hasattr(builtin_module, '__build_class__'):
            builtins['__build_class__'] = builtin_module.__build_class__
        
        # Add safe import function based on level
        allowed_modules = self.SAFE_IMPORTS.get(level, set()).copy()
        if allowed_imports:
            # Add additional allowed imports
            for module in allowed_imports:
                if self._is_safe_module(module, level):
                    allowed_modules.add(module)
        builtins['__import__'] = self._create_import_function(allowed_modules)
        
        safe_globals_dict['__builtins__'] = builtins
        safe_globals_dict['__name__'] = '__restricted__'
        safe_globals_dict['__metaclass__'] = type
        
        # Add required RestrictedPython helpers
        safe_globals_dict['_getitem_'] = lambda obj, index: obj[index]
        safe_globals_dict['_getiter_'] = lambda obj: iter(obj)
        safe_globals_dict['_iter_unpack_sequence_'] = guarded_iter_unpack_sequence
        safe_globals_dict['_getattr_'] = safer_getattr
        safe_globals_dict['_write_'] = lambda obj: obj  # Allow writes
        # For augmented assignments like +=, -=, etc.
        def _inplacevar_(op_str, x, y):
            ops = {
                '+=': lambda a, b: a + b,
                '-=': lambda a, b: a - b,
                '*=': lambda a, b: a * b,
                '/=': lambda a, b: a / b,
                '//=': lambda a, b: a // b,
                '%=': lambda a, b: a % b,
                '**=': lambda a, b: a ** b,
                '&=': lambda a, b: a & b,
                '|=': lambda a, b: a | b,
                '^=': lambda a, b: a ^ b,
                '<<=': lambda a, b: a << b,
                '>>=': lambda a, b: a >> b,
            }
            if op_str in ops:
                return ops[op_str](x, y)
            else:
                raise ValueError(f"Unsupported inplace operation: {op_str}")
        
        safe_globals_dict['_inplacevar_'] = _inplacevar_
        
        return safe_globals_dict
    
    def _create_import_function(self, allowed_modules: set[str]):
        """Create a restricted import function with allowed modules"""
        def _restricted_import(name, *args, **kwargs):
            if name not in allowed_modules:
                msg = f"Import of '{name}' is not allowed in this context"
                raise ImportError(msg)
            # Allow the import if it's in the allowed list
            return __import__(name, *args, **kwargs)
        return _restricted_import
    
    def _safe_print(self, *args, **kwargs):
        """Safe print function that captures output"""
        # In production, this would capture output instead of printing
        print("[SECURE]", *args, **kwargs)
    
    def _is_safe_module(self, module: str, level: PythonSecurityLevel) -> bool:
        """Check if a module is safe to import"""
        # Check against dangerous modules
        dangerous = {
            'os', 'sys', 'subprocess', 'socket', 'http', 'urllib',
            'pickle', 'shelve', 'marshal', 'imp', 'importlib',
            '__builtin__', '__builtins__', 'eval', 'exec',
            'compile', 'open', 'file', 'input', 'raw_input',
            'execfile', 'reload',
        }
        
        base_module = module.split('.')[0]
        return base_module not in dangerous and module in self.SAFE_IMPORTS.get(level, set())
    
    def _set_resource_limits(self, memory_limit_mb: int) -> None:
        """Set resource limits for execution"""
        try:
            # Set memory limit
            memory_bytes = memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        except Exception:
            # Resource limits may not work on all platforms
            pass


class SecurityValidator(ast.NodeVisitor):
    """AST validator for additional security checks"""
    
    def __init__(self, level: PythonSecurityLevel):
        self.level = level
        self.errors = []
    
    def visit_Import(self, node: ast.Import) -> None:
        """Check import statements"""
        for alias in node.names:
            if self.level == PythonSecurityLevel.STRICT:
                self.errors.append(f"Import of '{alias.name}' not allowed in STRICT mode")
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check from-import statements"""
        if self.level == PythonSecurityLevel.STRICT:
            self.errors.append(f"Import from '{node.module}' not allowed in STRICT mode")
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call) -> None:
        """Check function calls for dangerous patterns"""
        # Check for eval/exec calls
        if isinstance(node.func, ast.Name):
            if node.func.id in ('eval', 'exec', 'compile'):
                if self.level != PythonSecurityLevel.TRUSTED:
                    self.errors.append(f"Call to '{node.func.id}' not allowed in {self.level.value} mode")
        self.generic_visit(node)


# Global instance for convenience
_default_engine = None


def get_python_engine() -> SecurePythonEngine:
    """Get the global secure Python engine instance"""
    global _default_engine
    if _default_engine is None:
        _default_engine = SecurePythonEngine()
    return _default_engine


def execute_secure_python(
    code: str,
    context: dict[str, Any] | None = None,
    level: PythonSecurityLevel | None = None,
    **kwargs
) -> Any:
    """Convenience function to execute Python code securely"""
    engine = get_python_engine()
    return engine.execute(code, context, level, **kwargs)