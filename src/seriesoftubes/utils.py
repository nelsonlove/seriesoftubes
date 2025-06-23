"""Utility functions for seriesoftubes"""

from typing import Any


class DotDict:
    """Dictionary wrapper that allows safe dot notation access.
    
    This prevents ambiguity between dict keys and dict methods when using
    Jinja2 templates. For example, data.items will access the 'items' key
    rather than the items() method.
    """
    
    def __init__(self, data: dict[str, Any]):
        self._data = data
    
    def __getattr__(self, name: str) -> Any:
        """Get attribute from underlying dict, no fallback to methods"""
        if name.startswith('_'):
            # Allow access to our internal attributes
            return object.__getattribute__(self, name)
        
        if name in self._data:
            value = self._data[name]
            # Recursively wrap nested dicts
            if isinstance(value, dict):
                return DotDict(value)
            elif isinstance(value, list):
                # Wrap dicts inside lists too
                return [DotDict(item) if isinstance(item, dict) else item for item in value]
            return value
        
        # Return None for missing keys instead of raising AttributeError
        # This matches Jinja2's default behavior
        return None
    
    def __getitem__(self, key: str) -> Any:
        """Allow bracket notation access"""
        value = self._data[key]
        if isinstance(value, dict):
            return DotDict(value)
        elif isinstance(value, list):
            return [DotDict(item) if isinstance(item, dict) else item for item in value]
        return value
    
    def __contains__(self, key: str) -> bool:
        """Support 'in' operator"""
        return key in self._data
    
    def __repr__(self) -> str:
        return f"DotDict({self._data!r})"
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get with default value"""
        return self._data.get(key, default)
    
    # Explicitly don't expose dict methods like items(), keys(), values()
    # to avoid ambiguity in templates


def wrap_context_data(data: dict[str, Any]) -> dict[str, Any]:
    """Wrap context data for safe template access.
    
    Converts dict values to DotDict instances to ensure that dot notation
    in Jinja2 templates accesses keys rather than dict methods.
    """
    wrapped = {}
    for key, value in data.items():
        if isinstance(value, dict):
            wrapped[key] = DotDict(value)
        elif isinstance(value, list):
            # Wrap dicts inside lists
            wrapped[key] = [DotDict(item) if isinstance(item, dict) else item for item in value]
        else:
            wrapped[key] = value
    return wrapped