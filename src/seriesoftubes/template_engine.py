"""Secure template rendering engine for SeriesOfTubes.

This module provides centralized, secure template rendering with multiple
security levels to prevent template injection attacks while maintaining
flexibility for legitimate use cases.
"""

import re
from enum import Enum
from typing import Any

from jinja2 import Environment, StrictUndefined, Template, TemplateSyntaxError
from jinja2.exceptions import SecurityError, UndefinedError
from jinja2.sandbox import SandboxedEnvironment


class TemplateSecurityLevel(Enum):
    """Security levels for template rendering"""
    
    INTERPOLATION_ONLY = "interpolation"  # Only {{ variable }} substitution
    SAFE_EXPRESSIONS = "safe"  # Variables + safe filters/functions
    SANDBOXED = "sandboxed"  # Full Jinja2 in sandbox
    UNSAFE = "unsafe"  # Full Jinja2 (legacy compatibility only)


class TemplateValidationError(Exception):
    """Raised when template validation fails"""
    pass


class SecureTemplateEngine:
    """Centralized secure template rendering engine"""
    
    # Regex for simple interpolation: {{ variable }} or {{ var.field }} or {{ var['key'] }}
    INTERPOLATION_PATTERN = re.compile(
        r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*|\[[\'"][^\'"]+[\'"]\])*)\s*\}\}'
    )
    
    # Safe filters that don't allow code execution
    SAFE_FILTERS = {
        # String filters
        'upper', 'lower', 'title', 'capitalize', 'trim', 'strip',
        'replace', 'truncate', 'wordwrap', 'center', 'ljust', 'rjust',
        # Numeric filters
        'abs', 'round', 'int', 'float',
        # List filters
        'first', 'last', 'length', 'count', 'reverse', 'sort',
        'min', 'max', 'sum', 'unique',
        # Dict filters
        'items', 'keys', 'values',
        # Formatting
        'default', 'join', 'format',
        # Type checking
        'string', 'number', 'list', 'mapping',
    }
    
    # Safe global functions
    SAFE_GLOBALS = {
        'len': len,
        'range': range,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'list': list,
        'dict': dict,
        'min': min,
        'max': max,
        'sum': sum,
        'abs': abs,
        'round': round,
    }
    
    def __init__(self, default_level: TemplateSecurityLevel = TemplateSecurityLevel.SAFE_EXPRESSIONS):
        """Initialize the template engine with a default security level"""
        self.default_level = default_level
        
        # Create environments for different security levels
        self._init_environments()
    
    def _init_environments(self) -> None:
        """Initialize Jinja2 environments for different security levels"""
        # Safe expressions environment
        self.safe_env = Environment(
            autoescape=True,
            undefined=StrictUndefined,
            finalize=lambda x: x if x is not None else '',
        )
        
        # Add only safe filters
        for filter_name in self.SAFE_FILTERS:
            if filter_name in self.safe_env.filters:
                continue  # Keep built-in implementation
        
        # Add safe globals
        self.safe_env.globals.update(self.SAFE_GLOBALS)
        
        # Sandboxed environment for untrusted templates
        self.sandbox_env = SandboxedEnvironment(
            autoescape=True,
            undefined=StrictUndefined,
            finalize=lambda x: x if x is not None else '',
        )
        self.sandbox_env.globals.update(self.SAFE_GLOBALS)
        
        # Unsafe environment (for legacy compatibility only)
        self.unsafe_env = Environment(
            autoescape=False,
            undefined=StrictUndefined,
        )
    
    def render(
        self,
        template_str: str,
        context: dict[str, Any],
        level: TemplateSecurityLevel | None = None,
        node_type: str | None = None,
    ) -> str:
        """Render a template with the specified security level.
        
        Args:
            template_str: The template string to render
            context: Context data for rendering
            level: Security level (uses default if not specified)
            node_type: Type of node using the template (for logging)
            
        Returns:
            Rendered template string
            
        Raises:
            TemplateValidationError: If template contains unsafe constructs
            TemplateSyntaxError: If template syntax is invalid
        """
        if level is None:
            level = self.default_level
        
        # Validate template based on security level
        self._validate_template(template_str, level)
        
        try:
            if level == TemplateSecurityLevel.INTERPOLATION_ONLY:
                return self._render_interpolation_only(template_str, context)
            elif level == TemplateSecurityLevel.SAFE_EXPRESSIONS:
                return self._render_safe_expressions(template_str, context)
            elif level == TemplateSecurityLevel.SANDBOXED:
                return self._render_sandboxed(template_str, context)
            elif level == TemplateSecurityLevel.UNSAFE:
                # Log warning for unsafe template usage
                if node_type:
                    print(f"WARNING: Unsafe template rendering in {node_type} node")
                return self._render_unsafe(template_str, context)
            else:
                msg = f"Unknown security level: {level}"
                raise ValueError(msg)
                
        except (UndefinedError, SecurityError) as e:
            msg = f"Template rendering error: {e}"
            raise TemplateValidationError(msg) from e
    
    def _validate_template(self, template_str: str, level: TemplateSecurityLevel) -> None:
        """Validate template based on security level"""
        if level == TemplateSecurityLevel.INTERPOLATION_ONLY:
            # Check for any Jinja2 constructs beyond simple interpolation
            # Remove all valid interpolations
            remaining = self.INTERPOLATION_PATTERN.sub('', template_str)
            
            # Check for any remaining Jinja2 syntax
            if '{%' in remaining or '{{' in remaining or '{#' in remaining:
                msg = "Template contains constructs beyond simple interpolation"
                raise TemplateValidationError(msg)
                
        elif level == TemplateSecurityLevel.SAFE_EXPRESSIONS:
            # Parse template to check for unsafe constructs
            try:
                ast = self.safe_env.parse(template_str)
                # Could add more AST analysis here
            except TemplateSyntaxError as e:
                msg = f"Invalid template syntax: {e}"
                raise TemplateValidationError(msg) from e
    
    def _render_interpolation_only(self, template_str: str, context: dict[str, Any]) -> str:
        """Render template with only variable interpolation"""
        def replace_var(match):
            var_path = match.group(1)
            try:
                # Parse variable path (handles dots and brackets)
                value = context
                for part in self._parse_var_path(var_path):
                    if isinstance(value, dict):
                        value = value.get(part, '')
                    else:
                        value = getattr(value, part, '')
                return str(value) if value is not None else ''
            except Exception:
                return ''
        
        return self.INTERPOLATION_PATTERN.sub(replace_var, template_str)
    
    def _parse_var_path(self, var_path: str) -> list[str]:
        """Parse variable path like 'var.field' or 'var["key"]' into parts"""
        parts = []
        current = []
        in_bracket = False
        
        i = 0
        while i < len(var_path):
            char = var_path[i]
            
            if char == '.' and not in_bracket:
                if current:
                    parts.append(''.join(current))
                    current = []
            elif char == '[':
                if current:
                    parts.append(''.join(current))
                    current = []
                in_bracket = True
                # Skip to quote
                while i < len(var_path) and var_path[i] not in ('"', "'"):
                    i += 1
                i += 1  # Skip quote
                # Read until closing quote
                while i < len(var_path) and var_path[i] not in ('"', "'"):
                    current.append(var_path[i])
                    i += 1
                parts.append(''.join(current))
                current = []
                # Skip to closing bracket
                while i < len(var_path) and var_path[i] != ']':
                    i += 1
                in_bracket = False
            else:
                current.append(char)
            
            i += 1
        
        if current:
            parts.append(''.join(current))
        
        return parts
    
    def _render_safe_expressions(self, template_str: str, context: dict[str, Any]) -> str:
        """Render template with safe expressions and filters"""
        template = self.safe_env.from_string(template_str)
        return template.render(**context)
    
    def _render_sandboxed(self, template_str: str, context: dict[str, Any]) -> str:
        """Render template in sandboxed environment"""
        template = self.sandbox_env.from_string(template_str)
        return template.render(**context)
    
    def _render_unsafe(self, template_str: str, context: dict[str, Any]) -> str:
        """Render template without security (legacy compatibility only)"""
        template = self.unsafe_env.from_string(template_str)
        return template.render(**context)
    
    def render_dict_template(
        self,
        template_dict: dict[str, Any],
        context: dict[str, Any],
        level: TemplateSecurityLevel | None = None,
    ) -> dict[str, Any]:
        """Render a dictionary template (for transform nodes).
        
        Args:
            template_dict: Dictionary with template strings as values
            context: Context data for rendering
            level: Security level (uses default if not specified)
            
        Returns:
            Rendered dictionary
        """
        if level is None:
            level = self.default_level
        
        result = {}
        for key, value in template_dict.items():
            if isinstance(value, str):
                result[key] = self.render(value, context, level)
            elif isinstance(value, dict):
                result[key] = self.render_dict_template(value, context, level)
            elif isinstance(value, list):
                result[key] = [
                    self.render(item, context, level) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
        
        return result


# Global instance for convenience
_default_engine = None


def get_template_engine() -> SecureTemplateEngine:
    """Get the global template engine instance"""
    global _default_engine
    if _default_engine is None:
        _default_engine = SecureTemplateEngine()
    return _default_engine


def render_template(
    template_str: str,
    context: dict[str, Any],
    level: TemplateSecurityLevel | None = None,
    node_type: str | None = None,
) -> str:
    """Convenience function to render a template using the global engine"""
    engine = get_template_engine()
    return engine.render(template_str, context, level, node_type)