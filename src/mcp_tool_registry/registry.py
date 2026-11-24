"""Tool registry: register Python functions as tools, list them, call them safely."""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .schema import SchemaError, apply_defaults, validate

_PY_TO_JSON = {
    str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object",
    "str": "string", "int": "integer", "float": "number", "bool": "boolean", "list": "array", "dict": "object",
}


class ToolCallError(RuntimeError):
    """Raised when a tool call cannot be completed."""


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    func: Callable[..., Any]
    timeout_s: Optional[float] = None

    def spec(self) -> dict:
        """The tool as an MCP-style `tools/list` entry."""
        return {"name": self.name, "description": self.description, "inputSchema": self.input_schema}


def schema_from_signature(func: Callable[..., Any]) -> dict:
    """Build an object schema from a function's type hints and defaults."""
    props: dict = {}
    required: list = []
    for name, param in inspect.signature(func).parameters.items():
        prop: dict = {}
        json_type = _PY_TO_JSON.get(param.annotation)
        if json_type:
            prop["type"] = json_type
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            prop["default"] = param.default
        props[name] = prop
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


@dataclass
class ToolRegistry:
    tools: dict = field(default_factory=dict)
    call_log: list = field(default_factory=list)

    def register(self, func: Callable[..., Any], *, name: Optional[str] = None,
                 description: Optional[str] = None, input_schema: Optional[dict] = None,
                 timeout_s: Optional[float] = None) -> Tool:
        tool_name = name or func.__name__
        if tool_name in self.tools:
            raise ValueError(f"tool already registered: {tool_name}")
        desc = description or (inspect.getdoc(func) or "").split("\n")[0]
        t = Tool(tool_name, desc, input_schema or schema_from_signature(func), func, timeout_s)
        self.tools[tool_name] = t
        return t

    def tool(self, name: Optional[str] = None, **kwargs: Any) -> Callable:
        """Decorator form of register()."""
        def deco(func: Callable[..., Any]) -> Callable[..., Any]:
            self.register(func, name=name, **kwargs)
            return func
        return deco

    def list_tools(self) -> list:
        return [t.spec() for t in sorted(self.tools.values(), key=lambda t: t.name)]

    def call(self, name: str, arguments: Optional[dict] = None) -> dict:
        """Validate and run a tool. Returns an MCP-style result; never raises for tool errors."""
        arguments = arguments or {}
        start = time.perf_counter()
        if name not in self.tools:
            result = {"isError": True, "content": [{"type": "text", "text": f"unknown tool: {name}"}]}
        else:
            t = self.tools[name]
            try:
                validate(arguments, t.input_schema)
                args = apply_defaults(arguments, t.input_schema)
                value = t.func(**args)
                elapsed = time.perf_counter() - start
                if t.timeout_s is not None and elapsed > t.timeout_s:
                    raise ToolCallError(f"took {elapsed:.3f}s, limit {t.timeout_s}s")
                result = {"isError": False, "content": [{"type": "text", "text": str(value)}], "value": value}
            except SchemaError as e:
                result = {"isError": True, "content": [{"type": "text", "text": f"invalid arguments: {e}"}],
                          "errors": e.errors}
            except Exception as e:  # a tool bug must not crash the agent loop
                result = {"isError": True, "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}]}
        self.call_log.append({"tool": name, "arguments": arguments, "isError": result["isError"],
                              "ms": round((time.perf_counter() - start) * 1000, 3)})
        return result


_default = ToolRegistry()


def tool(name: Optional[str] = None, **kwargs: Any) -> Callable:
    """Register on the module-level default registry."""
    return _default.tool(name, **kwargs)
