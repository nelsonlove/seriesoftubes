"""Tests for the secure template engine"""

import pytest

from seriesoftubes.template_engine import (
    SecureTemplateEngine,
    TemplateSecurityLevel,
    TemplateValidationError,
)


class TestSecureTemplateEngine:
    """Test the secure template engine functionality"""

    def test_interpolation_only_simple(self):
        """Test simple variable interpolation"""
        engine = SecureTemplateEngine()
        template = "Hello {{ name }}, you have {{ count }} messages"
        context = {"name": "Alice", "count": 5}
        
        result = engine.render(
            template, context, level=TemplateSecurityLevel.INTERPOLATION_ONLY
        )
        assert result == "Hello Alice, you have 5 messages"

    def test_interpolation_only_nested(self):
        """Test nested variable access"""
        engine = SecureTemplateEngine()
        template = "Company: {{ company.name }}, Revenue: {{ company['revenue'] }}"
        context = {"company": {"name": "Acme Corp", "revenue": 1000000}}
        
        result = engine.render(
            template, context, level=TemplateSecurityLevel.INTERPOLATION_ONLY
        )
        assert result == "Company: Acme Corp, Revenue: 1000000"

    def test_interpolation_only_blocks_expressions(self):
        """Test that interpolation-only mode blocks expressions"""
        engine = SecureTemplateEngine()
        
        # Should block if statements
        with pytest.raises(TemplateValidationError):
            engine.render(
                "{% if true %}danger{% endif %}",
                {},
                level=TemplateSecurityLevel.INTERPOLATION_ONLY
            )
        
        # Should block for loops
        with pytest.raises(TemplateValidationError):
            engine.render(
                "{% for item in items %}{{ item }}{% endfor %}",
                {"items": [1, 2, 3]},
                level=TemplateSecurityLevel.INTERPOLATION_ONLY
            )
        
        # Should block filters
        with pytest.raises(TemplateValidationError):
            engine.render(
                "{{ name | upper }}",
                {"name": "test"},
                level=TemplateSecurityLevel.INTERPOLATION_ONLY
            )

    def test_safe_expressions_filters(self):
        """Test safe expression mode with filters"""
        engine = SecureTemplateEngine()
        
        # String filters
        template = "{{ name | upper }}, {{ text | lower }}"
        context = {"name": "alice", "text": "HELLO"}
        result = engine.render(
            template, context, level=TemplateSecurityLevel.SAFE_EXPRESSIONS
        )
        assert result == "ALICE, hello"
        
        # Default filter
        template = "Hello {{ name | default('Guest') }}"
        result = engine.render(
            template, {}, level=TemplateSecurityLevel.SAFE_EXPRESSIONS
        )
        assert result == "Hello Guest"

    def test_safe_expressions_conditions(self):
        """Test safe expressions with simple conditions"""
        engine = SecureTemplateEngine()
        
        template = "{% if score > 80 %}Pass{% else %}Fail{% endif %}"
        
        result = engine.render(
            template, {"score": 90}, level=TemplateSecurityLevel.SAFE_EXPRESSIONS
        )
        assert result == "Pass"
        
        result = engine.render(
            template, {"score": 70}, level=TemplateSecurityLevel.SAFE_EXPRESSIONS
        )
        assert result == "Fail"

    def test_dict_template_rendering(self):
        """Test rendering dictionary templates"""
        engine = SecureTemplateEngine()
        
        template_dict = {
            "name": "{{ user.name | upper }}",
            "email": "{{ user.email | lower }}",
            "score": "{{ user.score * 100 }}",
            "nested": {
                "id": "{{ user.id }}",
                "status": "{% if user.active %}Active{% else %}Inactive{% endif %}"
            }
        }
        
        context = {
            "user": {
                "name": "Alice",
                "email": "ALICE@EXAMPLE.COM",
                "score": 0.95,
                "id": 123,
                "active": True
            }
        }
        
        result = engine.render_dict_template(
            template_dict, context, level=TemplateSecurityLevel.SAFE_EXPRESSIONS
        )
        
        assert result["name"] == "ALICE"
        assert result["email"] == "alice@example.com"
        assert result["score"] == "95.0"
        assert result["nested"]["id"] == "123"
        assert result["nested"]["status"] == "Active"

    def test_undefined_variables(self):
        """Test handling of undefined variables"""
        engine = SecureTemplateEngine()
        
        # Interpolation mode returns empty string for undefined
        result = engine.render(
            "Hello {{ undefined_var }}",
            {},
            level=TemplateSecurityLevel.INTERPOLATION_ONLY
        )
        assert result == "Hello "
        
        # Safe expressions mode raises error for undefined
        with pytest.raises(TemplateValidationError):
            engine.render(
                "Hello {{ undefined_var }}",
                {},
                level=TemplateSecurityLevel.SAFE_EXPRESSIONS
            )

    def test_security_levels(self):
        """Test different security levels"""
        engine = SecureTemplateEngine()
        context = {"items": [1, 2, 3]}
        
        # Interpolation only - can't use loops
        with pytest.raises(TemplateValidationError):
            engine.render(
                "{% for item in items %}{{ item }}{% endfor %}",
                context,
                level=TemplateSecurityLevel.INTERPOLATION_ONLY
            )
        
        # Safe expressions - can use loops
        result = engine.render(
            "{% for item in items %}{{ item }} {% endfor %}",
            context,
            level=TemplateSecurityLevel.SAFE_EXPRESSIONS
        )
        assert result.strip() == "1 2 3"

    def test_node_type_logging(self, capsys):
        """Test that node type is logged for unsafe templates"""
        engine = SecureTemplateEngine()
        
        # Using unsafe level should log warning
        engine.render(
            "{{ name }}",
            {"name": "test"},
            level=TemplateSecurityLevel.UNSAFE,
            node_type="test-node"
        )
        
        captured = capsys.readouterr()
        assert "WARNING: Unsafe template rendering in test-node node" in captured.out