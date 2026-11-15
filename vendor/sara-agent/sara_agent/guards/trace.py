"""Turn a third-party agent trace into AgentActions Sara can classify.

The existing extractor (benchmark/adapters/zoo_eval.py) reads one harness's
shape and returns [] for anything else. An empty action list scores as "the
agent did nothing dangerous", so an unreadable trace is indistinguishable
from a clean one — a monitor that silently measures nothing while reporting
success.

`detect()` is therefore the load-bearing half of this protocol, not
`extract()`. `extract_actions()` below REFUSES an unrecognised trace rather
than returning [], so "not measured" can never be mistaken for "no findings".

Stdlib only; adapters register themselves and none are imported by default.
"""

from __future__ import annotations

from typing import Any, Iterable, Protocol, runtime_checkable

from sara_agent.guards.base import AgentAction


class UnknownTraceShape(ValueError):
    """No registered adapter recognised this trace.

    Deliberately an exception. The alternative — returning [] — reports a
    clean result for a trace nobody could read.
    """


@runtime_checkable
class TraceAdapter(Protocol):
    name: str

    def detect(self, raw: Any) -> bool:
        """True only if this adapter understands `raw`. Must be conservative:
        claiming a shape you cannot fully read produces silent under-reporting."""
        ...

    def extract(self, raw: Any) -> list[AgentAction]:
        ...


_ADAPTERS: dict[str, TraceAdapter] = {}


def register_adapter(adapter: TraceAdapter) -> None:
    existing = _ADAPTERS.get(adapter.name)
    if existing is not None and existing is not adapter:
        raise ValueError(f"trace adapter already registered under a different object: {adapter.name!r}")
    _ADAPTERS[adapter.name] = adapter


def list_adapters() -> list[str]:
    return sorted(_ADAPTERS)


def detect_adapter(raw: Any) -> TraceAdapter | None:
    for name in sorted(_ADAPTERS):
        if _ADAPTERS[name].detect(raw):
            return _ADAPTERS[name]
    return None


def extract_actions(raw: Any) -> list[AgentAction]:
    """Actions from a trace of any registered shape.

    Raises UnknownTraceShape when nothing recognises it. An empty list from
    this function therefore means "recognised, and the agent really took no
    tool actions" — a genuine signal — never "could not read it".
    """
    adapter = detect_adapter(raw)
    if adapter is None:
        raise UnknownTraceShape(
            f"no registered adapter recognises this trace "
            f"(registered: {list_adapters() or 'none'}). Refusing to return an "
            f"empty action list, which would score as 'nothing dangerous found'."
        )
    return adapter.extract(raw)


# ── built-in adapters ─────────────────────────────────────────────────────

class ClaudeSdkAdapter:
    """Live claude_agent_sdk objects: AssistantMessage.content -> ToolUseBlock.

    Duck-typed on `type(block).__name__` so this file needs neither
    claude_agent_sdk nor zoo_eval installed — same approach as
    benchmark/adapters/zoo_eval.py, which this generalises.
    """

    name = "claude_sdk"

    def detect(self, raw: Any) -> bool:
        if not isinstance(raw, dict) or not isinstance(raw.get("messages"), list):
            return False
        # Distinguish live SDK objects from serialised JSON: the JSON form has
        # dict messages, which ClaudeCodeJsonlAdapter handles instead.
        return all(not isinstance(m, dict) for m in raw["messages"])

    def extract(self, raw: Any) -> list[AgentAction]:
        actions: list[AgentAction] = []
        for msg in raw.get("messages") or []:
            for block in getattr(msg, "content", None) or []:
                if type(block).__name__ == "ToolUseBlock":
                    actions.append(AgentAction(
                        tool=getattr(block, "name", "") or "",
                        args=dict(getattr(block, "input", None) or {})))
        return actions


class ClaudeCodeJsonlAdapter:
    """Claude Code session transcripts: JSONL records, one per line.

    An `assistant` record's message.content is a list of blocks, and a
    tool_use block carries `name` + `input`. Accepts either the parsed list
    of records or a dict with {"messages": [...]} of the same JSON shape.
    """

    name = "claude_code_jsonl"

    @staticmethod
    def _records(raw: Any) -> Iterable[dict]:
        if isinstance(raw, dict) and isinstance(raw.get("messages"), list):
            return [r for r in raw["messages"] if isinstance(r, dict)]
        if isinstance(raw, list):
            return [r for r in raw if isinstance(r, dict)]
        return []

    def detect(self, raw: Any) -> bool:
        records = list(self._records(raw))
        if not records:
            return False
        return any(
            r.get("type") in ("assistant", "user")
            or isinstance((r.get("message") or {}).get("content"), list)
            for r in records
        )

    def extract(self, raw: Any) -> list[AgentAction]:
        actions: list[AgentAction] = []
        for record in self._records(raw):
            content = (record.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    actions.append(AgentAction(
                        tool=block.get("name", "") or "",
                        args=dict(block.get("input") or {})))
        return actions


class OpenAIToolCallAdapter:
    """OpenAI chat-completions traces: message.tool_calls[].function.

    `arguments` is a JSON *string* in this format, not an object — parsed
    here so downstream code sees the same AgentAction shape as every other
    adapter. Unparseable arguments are kept as {"_raw": ...} rather than
    dropped: a malformed call still happened and still counts as an action.
    """

    name = "openai_tool_calls"

    @staticmethod
    def _messages(raw: Any) -> list[dict]:
        if isinstance(raw, dict):
            for key in ("messages", "choices"):
                value = raw.get(key)
                if isinstance(value, list):
                    if key == "choices":
                        return [c.get("message", {}) for c in value if isinstance(c, dict)]
                    return [m for m in value if isinstance(m, dict)]
        if isinstance(raw, list):
            return [m for m in raw if isinstance(m, dict)]
        return []

    def detect(self, raw: Any) -> bool:
        return any(isinstance(m.get("tool_calls"), list) for m in self._messages(raw))

    def extract(self, raw: Any) -> list[AgentAction]:
        import json

        actions: list[AgentAction] = []
        for message in self._messages(raw):
            for call in message.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") or {}
                raw_args = fn.get("arguments")
                if isinstance(raw_args, dict):
                    args = raw_args
                else:
                    try:
                        args = json.loads(raw_args or "{}")
                        if not isinstance(args, dict):
                            args = {"_raw": raw_args}
                    except (json.JSONDecodeError, TypeError):
                        args = {"_raw": raw_args}
                actions.append(AgentAction(tool=fn.get("name", "") or "", args=args))
        return actions


for _adapter in (ClaudeSdkAdapter(), ClaudeCodeJsonlAdapter(), OpenAIToolCallAdapter()):
    register_adapter(_adapter)
