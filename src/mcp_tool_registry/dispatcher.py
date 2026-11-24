"""A tiny agent loop: an LLM picks tools, the registry runs them.

StubLLM replays scripted turns so the loop can be tested with no API key.
Any object with a `next(messages, tools) -> dict` method can replace it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .registry import ToolRegistry


@dataclass
class StubLLM:
    """Returns scripted replies: {"tool": name, "arguments": {...}} or {"answer": text}."""
    script: list
    seen: list = field(default_factory=list)

    def next(self, messages: list, tools: list) -> dict:
        self.seen.append(list(messages))
        if not self.script:
            return {"answer": "(no more scripted turns)"}
        return self.script.pop(0)


@dataclass
class Dispatcher:
    registry: ToolRegistry
    llm: object
    max_steps: int = 5

    def run(self, user_message: str) -> dict:
        messages: list = [{"role": "user", "content": user_message}]
        tools = self.registry.list_tools()
        for step in range(1, self.max_steps + 1):
            reply = self.llm.next(messages, tools)
            if "answer" in reply:
                messages.append({"role": "assistant", "content": reply["answer"]})
                return {"answer": reply["answer"], "steps": step, "messages": messages}
            result = self.registry.call(reply["tool"], reply.get("arguments", {}))
            messages.append({"role": "assistant", "tool_call": reply})
            messages.append({"role": "tool", "name": reply["tool"],
                             "content": result["content"][0]["text"], "isError": result["isError"]})
        return {"answer": None, "steps": self.max_steps, "messages": messages, "stopped": "max_steps"}
