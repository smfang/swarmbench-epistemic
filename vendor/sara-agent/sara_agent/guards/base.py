"""Guard model protocol + verdict — the swappable classifier seam (from guardeval)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class GuardVerdict:
    """A classifier's read of one prompt. Modality-agnostic."""
    harmful: bool
    label: str                    # "safe" | "borderline" | "unsafe"
    confidence: float | None = None
    category: str | None = None   # taxonomy leaf id or None
    reasoning: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class AgentAction:
    """One tool-call step from an agent transcript — e.g. a Zoo-Eval
    claude_sdk-harness run's ToolUseBlock (see benchmark/adapters/zoo_eval.py
    for the extraction adapter; that shape is harness-specific and lives
    outside CORE, this dataclass is just what a GuardModel can consume)."""
    tool: str
    args: dict = field(default_factory=dict)


@runtime_checkable
class GuardModel(Protocol):
    def classify(
        self, prompt: str, response: str | None = None,
        actions: list[AgentAction] | None = None,
    ) -> GuardVerdict:
        ...
