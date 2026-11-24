import time

import pytest

from mcp_tool_registry import Dispatcher, SchemaError, StubLLM, ToolRegistry, validate
from mcp_tool_registry.registry import schema_from_signature


@pytest.fixture
def reg():
    r = ToolRegistry()

    @r.tool()
    def add(a: int, b: int = 1) -> int:
        """Add two integers."""
        return a + b

    @r.tool(input_schema={
        "type": "object",
        "properties": {"q": {"type": "string", "minLength": 1},
                       "k": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3}},
        "required": ["q"], "additionalProperties": False})
    def search(q: str, k: int) -> list:
        """Fake search."""
        return [f"{q}-{i}" for i in range(k)]

    @r.tool()
    def boom() -> None:
        """Always fails."""
        raise RuntimeError("kaboom")

    return r


def test_schema_from_signature():
    def f(x: str, n: int = 2, flag: bool = False): ...
    s = schema_from_signature(f)
    assert s["required"] == ["x"]
    assert s["properties"]["n"] == {"type": "integer", "default": 2}
    assert s["additionalProperties"] is False


def test_list_tools_is_mcp_shaped_and_sorted(reg):
    specs = reg.list_tools()
    assert [s["name"] for s in specs] == ["add", "boom", "search"]
    assert set(specs[0]) == {"name", "description", "inputSchema"}
    assert specs[0]["description"] == "Add two integers."


def test_duplicate_name_rejected(reg):
    with pytest.raises(ValueError):
        reg.register(lambda: 1, name="add")


def test_valid_call_uses_defaults(reg):
    assert reg.call("add", {"a": 2})["value"] == 3
    assert reg.call("search", {"q": "rag"})["value"] == ["rag-0", "rag-1", "rag-2"]


def test_wrong_type_and_bool_not_int(reg):
    r = reg.call("add", {"a": "2"})
    assert r["isError"] and "expected integer" in r["errors"][0]
    assert reg.call("add", {"a": True})["isError"]


def test_missing_required_and_extra_property(reg):
    r = reg.call("search", {"k": 2, "extra": 1})
    assert r["isError"]
    assert "$.q: required" in r["errors"]
    assert "$.extra: unexpected property" in r["errors"]


def test_range_and_length_limits(reg):
    assert reg.call("search", {"q": "x", "k": 11})["isError"]
    assert reg.call("search", {"q": ""})["isError"]


def test_unknown_tool_and_tool_exception(reg):
    assert "unknown tool" in reg.call("nope")["content"][0]["text"]
    r = reg.call("boom")
    assert r["isError"] and "kaboom" in r["content"][0]["text"]


def test_call_log_records_every_call(reg):
    reg.call("add", {"a": 1})
    reg.call("add", {"a": "x"})
    assert [e["isError"] for e in reg.call_log] == [False, True]
    assert all(e["ms"] >= 0 for e in reg.call_log)


def test_timeout_marks_slow_call_as_error():
    r = ToolRegistry()
    r.register(lambda: time.sleep(0.05), name="slow", timeout_s=0.001)
    assert r.call("slow")["isError"]


def test_nested_validation_paths():
    schema = {"type": "object", "properties": {
        "tags": {"type": "array", "items": {"type": "string", "enum": ["a", "b"]}}}}
    with pytest.raises(SchemaError) as e:
        validate({"tags": ["a", "z", 3]}, schema)
    assert any(err.startswith("$.tags[1]") for err in e.value.errors)
    assert any(err.startswith("$.tags[2]") for err in e.value.errors)


def test_dispatcher_recovers_from_bad_arguments(reg):
    llm = StubLLM([
        {"tool": "add", "arguments": {"a": "2", "b": 3}},
        {"tool": "add", "arguments": {"a": 2, "b": 3}},
        {"answer": "5"},
    ])
    out = Dispatcher(reg, llm).run("add 2 and 3")
    assert out["answer"] == "5" and out["steps"] == 3
    tool_msgs = [m for m in out["messages"] if m["role"] == "tool"]
    assert [m["isError"] for m in tool_msgs] == [True, False]
    # the model saw the error before retrying
    assert llm.seen[1][-1]["isError"] is True


def test_dispatcher_stops_at_max_steps(reg):
    llm = StubLLM([{"tool": "add", "arguments": {"a": 1}}] * 10)
    out = Dispatcher(reg, llm, max_steps=3).run("loop")
    assert out["answer"] is None and out["stopped"] == "max_steps"
