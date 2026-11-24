"""A small MCP-style tool registry with JSON-schema argument validation."""

from .schema import SchemaError, validate
from .registry import Tool, ToolRegistry, ToolCallError, tool
from .dispatcher import Dispatcher, StubLLM

__all__ = [
    "SchemaError",
    "validate",
    "Tool",
    "ToolRegistry",
    "ToolCallError",
    "tool",
    "Dispatcher",
    "StubLLM",
]
__version__ = "0.1.0"
