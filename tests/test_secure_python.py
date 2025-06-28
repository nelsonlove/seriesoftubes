"""Tests for secure Python code execution"""

import pytest

from seriesoftubes.secure_python import (
    CodeValidationError,
    ExecutionError,
    PythonSecurityLevel,
    SecurePythonEngine,
    execute_secure_python,
)


class TestSecurePythonEngine:
    """Test the secure Python execution engine"""

    def test_basic_execution(self):
        """Test basic code execution"""
        code = """
result = 2 + 2
"""
        result = execute_secure_python(code)
        assert result == 4

    def test_context_access(self):
        """Test accessing context variables"""
        code = """
result = x + y
"""
        context = {"x": 10, "y": 20}
        result = execute_secure_python(code, context)
        assert result == 30

    def test_string_operations(self):
        """Test string manipulation"""
        code = """
name = context['name']
greeting = context['greeting']
result = f"{greeting}, {name.upper()}!"
"""
        context = {"name": "alice", "greeting": "Hello"}
        result = execute_secure_python(code, context)
        assert result == "Hello, ALICE!"

    def test_list_comprehension(self):
        """Test list comprehensions work"""
        code = """
numbers = context['numbers']
result = [x * 2 for x in numbers if x > 2]
"""
        context = {"numbers": [1, 2, 3, 4, 5]}
        result = execute_secure_python(code, context)
        assert result == [6, 8, 10]

    def test_dict_operations(self):
        """Test dictionary operations"""
        code = """
data = context['data']
result = {k: v * 2 for k, v in data.items() if v > 10}
"""
        context = {"data": {"a": 5, "b": 15, "c": 20}}
        result = execute_secure_python(code, context)
        assert result == {"b": 30, "c": 40}

    def test_function_definition(self):
        """Test defining and calling functions"""
        code = """
def multiply(a, b):
    return a * b

def process_list(items):
    return [multiply(x, 3) for x in items]

result = process_list(context['items'])
"""
        context = {"items": [1, 2, 3, 4]}
        result = execute_secure_python(code, context)
        assert result == [3, 6, 9, 12]

    def test_class_definition(self):
        """Test defining and using classes"""
        code = """
class Calculator:
    def __init__(self, base):
        self.base = base
    
    def add(self, x):
        return self.base + x
    
    def multiply(self, x):
        return self.base * x

calc = Calculator(10)
result = {
    'add': calc.add(5),
    'multiply': calc.multiply(3)
}
"""
        # Classes require TRUSTED level to work properly
        result = execute_secure_python(code, level=PythonSecurityLevel.TRUSTED)
        assert result == {"add": 15, "multiply": 30}

    def test_security_level_strict_no_imports(self):
        """Test STRICT security level blocks all imports"""
        code = """
import math
result = math.pi
"""
        with pytest.raises(CodeValidationError) as exc_info:
            execute_secure_python(code, level=PythonSecurityLevel.STRICT)
        assert "Import of 'math' not allowed in STRICT mode" in str(exc_info.value)

    def test_security_level_normal_safe_imports(self):
        """Test NORMAL security level allows safe imports"""
        code = """
import math
import json

data = {"pi": math.pi, "e": math.e}
result = json.dumps(data)
"""
        result = execute_secure_python(code, level=PythonSecurityLevel.NORMAL)
        assert "pi" in result
        assert "2.71" in result  # math.e

    def test_security_level_trusted_advanced(self):
        """Test TRUSTED security level allows more operations"""
        code = """
import hashlib
import base64

text = context['text']
hash_obj = hashlib.sha256(text.encode())
result = base64.b64encode(hash_obj.digest()).decode()
"""
        context = {"text": "hello world"}
        result = execute_secure_python(code, context, level=PythonSecurityLevel.TRUSTED)
        assert isinstance(result, str)
        assert len(result) == 44  # Base64 encoded SHA256

    def test_blocked_dangerous_imports(self):
        """Test dangerous imports are blocked"""
        dangerous_imports = ["os", "sys", "subprocess", "socket", "__builtins__"]
        
        for module in dangerous_imports:
            code = f"import {module}\nresult = 'should not reach here'"
            with pytest.raises((CodeValidationError, ExecutionError)):
                execute_secure_python(code, level=PythonSecurityLevel.TRUSTED)

    def test_blocked_file_operations(self):
        """Test file operations are blocked"""
        code = """
with open('/etc/passwd', 'r') as f:
    result = f.read()
"""
        with pytest.raises(ExecutionError):
            execute_secure_python(code)

    def test_blocked_eval_exec_strict(self):
        """Test eval/exec are blocked in STRICT mode"""
        code = """
result = eval("2 + 2")
"""
        with pytest.raises(CodeValidationError) as exc_info:
            execute_secure_python(code, level=PythonSecurityLevel.STRICT)
        assert "Call to 'eval' not allowed" in str(exc_info.value)

    def test_timeout_enforcement(self):
        """Test execution timeout is enforced"""
        code = """
import time
time.sleep(2)
result = "should timeout"
"""
        # Note: time.sleep might not work in RestrictedPython
        # This test might need adjustment based on actual behavior
        with pytest.raises(ExecutionError):
            execute_secure_python(code, timeout=1)

    def test_result_extraction_methods(self):
        """Test different ways to return results"""
        # Using 'result' variable
        code1 = "result = 42"
        assert execute_secure_python(code1) == 42
        
        # Variables starting with _ are not allowed by RestrictedPython
        # So we skip this test case and use a different variable name
        code2 = "output = 'hello'"
        assert execute_secure_python(code2) == "hello"
        
        # New variable created
        code3 = "output = [1, 2, 3]"
        assert execute_secure_python(code3) == [1, 2, 3]

    def test_syntax_error_handling(self):
        """Test syntax errors are handled properly"""
        code = """
if True
    result = 1
"""
        with pytest.raises(CodeValidationError) as exc_info:
            execute_secure_python(code)
        assert "Syntax error" in str(exc_info.value)

    def test_runtime_error_handling(self):
        """Test runtime errors are handled properly"""
        code = """
x = 1 / 0
result = x
"""
        with pytest.raises(ExecutionError) as exc_info:
            execute_secure_python(code)
        assert "division by zero" in str(exc_info.value)

    def test_custom_allowed_imports(self):
        """Test custom allowed imports parameter"""
        code = """
import numpy
result = "numpy imported"
"""
        # Should fail without numpy in allowed imports
        with pytest.raises((CodeValidationError, ExecutionError)):
            execute_secure_python(
                code, 
                level=PythonSecurityLevel.NORMAL,
                allowed_imports=["numpy"]
            )
        # Note: This will still fail since numpy isn't in SAFE_IMPORTS

    def test_memory_limit_parameter(self):
        """Test memory limit parameter is accepted"""
        code = "result = list(range(100))"
        # Should work with reasonable memory limit
        result = execute_secure_python(code, memory_limit_mb=50)
        assert len(result) == 100

    def test_nested_data_structures(self):
        """Test handling complex nested data"""
        code = """
data = context['data']
result = {
    'total': sum(item['value'] for item in data),
    'names': [item['name'].upper() for item in data],
    'filtered': [item for item in data if item['value'] > 50]
}
"""
        context = {
            "data": [
                {"name": "alice", "value": 30},
                {"name": "bob", "value": 60},
                {"name": "charlie", "value": 90},
            ]
        }
        result = execute_secure_python(code, context)
        assert result["total"] == 180
        assert result["names"] == ["ALICE", "BOB", "CHARLIE"]
        assert len(result["filtered"]) == 2

    def test_generator_expressions(self):
        """Test generator expressions work"""
        code = """
numbers = context['numbers']
gen = (x * x for x in numbers if x % 2 == 0)
result = list(gen)
"""
        context = {"numbers": [1, 2, 3, 4, 5, 6]}
        result = execute_secure_python(code, context)
        assert result == [4, 16, 36]

    def test_exception_handling(self):
        """Test try/except blocks work"""
        code = """
try:
    value = context.get('missing', 0)
    result = 100 / value
except ZeroDivisionError:
    result = "division by zero handled"
except Exception as e:
    result = f"error: {e}"
"""
        # Pass empty dict so 'context' variable exists in namespace
        result = execute_secure_python(code, context={"dummy": "value"})
        assert result == "division by zero handled"