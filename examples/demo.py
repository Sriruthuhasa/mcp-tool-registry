"""Run from the repo root: python examples/demo.py  (no API key needed)"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp_tool_registry import Dispatcher, StubLLM, ToolRegistry  # noqa: E402

reg = ToolRegistry()


@reg.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@reg.tool(input_schema={
    "type": "object",
    "properties": {"city": {"type": "string", "minLength": 2},
                   "unit": {"type": "string", "enum": ["C", "F"], "default": "C"}},
    "required": ["city"],
    "additionalProperties": False,
})
def weather(city: str, unit: str = "C") -> str:
    """Fake weather lookup."""
    return f"{city}: 21 {unit}"


print(json.dumps(reg.list_tools(), indent=2))

llm = StubLLM([
    {"tool": "add", "arguments": {"a": "2", "b": 3}},  # bad type -> error goes back to the model
    {"tool": "add", "arguments": {"a": 2, "b": 3}},
    {"tool": "weather", "arguments": {"city": "Austin"}},
    {"answer": "2 + 3 = 5 and Austin is 21 C."},
])
out = Dispatcher(reg, llm).run("Add 2 and 3, then check Austin weather.")
for m in out["messages"]:
    print(m)
print("call log:", reg.call_log)
