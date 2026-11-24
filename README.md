# mcp-tool-registry

A small, dependency-free Python library for giving an LLM agent a set of tools the
way MCP servers do: register functions, list them as `tools/list` specs, and run
calls only after the arguments pass JSON-schema validation.

Runs with no API keys. The agent loop uses a `StubLLM` that replays scripted
turns, so you can test tool-calling behaviour offline and swap in a real model later.

## What it does

- **Register tools** with a decorator. The input schema is built from type hints
  and defaults, or you pass your own JSON schema.
- **List tools** in MCP shape: `{"name", "description", "inputSchema"}`.
- **Validate arguments** before the function runs: `type`, `required`,
  `additionalProperties`, `enum`, `minimum`/`maximum`, `minLength`/`maxLength`,
  nested `items`. Every problem is reported with a path like `$.tags[2]`.
  `True` is not accepted as an integer.
- **Safe calls**: bad arguments, unknown tools, exceptions and slow calls
  come back as `{"isError": true, ...}` results instead of crashing the agent loop,
  so the model can read the error and retry.
- **Call log** with tool name, arguments, error flag and time in ms.
- **Dispatcher**: a tiny agent loop (model picks a tool, registry runs it,
  result goes back to the model) with a `max_steps` stop.

## Install

```bash
git clone https://github.com/Sriruthuhasa/mcp-tool-registry.git
cd mcp-tool-registry
pip install -e ".[dev]"
```

Python 3.9+. No runtime dependencies.

## Usage

```python
from mcp_tool_registry import Dispatcher, StubLLM, ToolRegistry

reg = ToolRegistry()

@reg.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b

print(reg.list_tools())
# [{'name': 'add', 'description': 'Add two integers.', 'inputSchema': {...}}]

print(reg.call("add", {"a": "2", "b": 3})["content"][0]["text"])
# invalid arguments: $.a: expected integer, got str

llm = StubLLM([
    {"tool": "add", "arguments": {"a": "2", "b": 3}},  # wrong type, gets an error back
    {"tool": "add", "arguments": {"a": 2, "b": 3}},    # retries correctly
    {"answer": "5"},
])
out = Dispatcher(reg, llm).run("add 2 and 3")
print(out["answer"], out["steps"])  # 5 3
```

A fuller example is in `examples/demo.py`:

```bash
python examples/demo.py
```

To use a real model, pass any object with a `next(messages, tools) -> dict`
method that returns `{"tool": name, "arguments": {...}}` or `{"answer": text}`.

## Run tests

```bash
pytest -q
```

## License

MIT, see [LICENSE](LICENSE).
