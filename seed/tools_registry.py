"""Tool registry for automatic discovery and hot reload."""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, Dict, List

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def tool_metadata(description: str = "", params: Dict[str, Any] = None):
    """Decorator to add tool metadata for auto-discovery."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Store metadata
        wrapper.__tool_metadata__ = {
            'description': description or func.__doc__ or 'No description',
            'params': params or _extract_parameters(func),
            'auto_discover': True
        }
        return wrapper
    return decorator


def _extract_parameters(func: Callable) -> Dict[str, Any]:
    """Extract function parameters for tool metadata."""
    sig = inspect.signature(func)
    parameters = {}
    for param_name, param in sig.parameters.items():
        if param_name not in ('self', 'args', 'kwargs'):
            parameters[param_name] = {
                'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'string',
                'required': param.default == inspect.Parameter.empty
            }
    return parameters


def discover_tools(module: Any) -> List[Dict[str, Any]]:
    """Discover all tools in a module with metadata."""
    tools = []
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        if hasattr(obj, '__tool_metadata__'):
            metadata = obj.__tool_metadata__
            tools.append({
                'name': name,
                'description': metadata['description'],
                'params': metadata['params'],
                'module': module.__name__
            })
    return tools


def register_tools(module: Any, registry: List[str]) -> None:
    """Register discovered tools in the global registry."""
    tools = discover_tools(module)
    for tool in tools:
        if tool['name'] not in registry:
            registry.append(tool['name'])
            print(f"🔧 Registered: {tool['name']}")