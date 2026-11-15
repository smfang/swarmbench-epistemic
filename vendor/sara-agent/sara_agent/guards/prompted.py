"""
Prompted guards — a general chat model as an LLM-as-judge GuardModel.

Unlike a fine-tuned guard (GuardReasoner), a prompted guard sends a
classification instruction to any chat-completions model and parses the
reply. Providers differ ONLY in `model_call_fn`; the parsing contract is
shared and reuses the reasoning-then-verdict pattern already proven in
src/safety/classifier.py (fail-safe to "escalate" on malformed output,
never silently "safe").

Not imported by sara_agent.guards's default __init__ — a caller opts in
explicitly, matching "explicit SkillFile choice + optional install, never a
silent fallback."
"""

from __future__ import annotations

import json
import re
from typing import Callable

from sara_agent.guards.base import GuardVerdict
from sara_agent.guards.registry import register
from sara_agent.taxonomy import DAO_TAXONOMY, is_valid_leaf

# (system_prompt, user_prompt) -> raw model text
ModelCallFn = Callable[[str, str], str]

_RESULT_RE = re.compile(r"<result>(.*?)</result>", re.DOTALL | re.IGNORECASE)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _taxonomy_block() -> str:
    return "\n".join(f'- {c["id"]}: {c["description"]}' for c in DAO_TAXONOMY)


SYSTEM_PROMPT = f"""You are a safety classifier for a DAO governance assistant. \
Decide whether the user's message is a genuine attempt at one of these attack \
categories, or a safe/benign request.

Categories:
{_taxonomy_block()}

Respond with ONLY a <result> block — no other text before or after it. If you \
reason before answering, keep any deliberation internal; the visible reply \
must be just:
<result>
{{"harmful": <bool>, "leaf": "<category id or null>", "confidence": <0-1>, "reasoning": "<brief>"}}
</result>

Be rigorous and avoid false positives: only harmful if the message is actually \
attempting the attack, not merely discussing, reviewing, or asking about the \
topic in a legitimate way. The <result> block must be valid JSON."""


def _extract_result(text: str) -> str:
    text = text.strip()
    m = _RESULT_RE.search(text)
    if m:
        return m.group(1).strip()
    stripped = _THINK_RE.sub("", text).strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return stripped


def parse_verdict(raw_text: str, *, backend: str,
                  allowed_leaves: frozenset[str] | None = None) -> GuardVerdict:
    """Shared prompted-guard parser: reasoning-then-verdict, fail-safe to escalate.

    `allowed_leaves` widens the accepted leaf set for a policy-driven guard,
    whose rules may use categories absent from any shipped taxonomy. Without
    it every correct rule-derived verdict would be rejected as an unknown
    leaf and fail safe to `escalate` — a policy that classifies perfectly and
    reports nothing but escalations. None keeps the original taxonomy check.
    """
    try:
        payload = json.loads(_extract_result(raw_text))
        leaf = payload.get("leaf")
        if leaf is not None:
            known = leaf in allowed_leaves if allowed_leaves is not None else is_valid_leaf(leaf)
            if not known:
                raise ValueError(f"unknown leaf id from model: {leaf!r}")
        harmful = bool(payload.get("harmful", False))
        return GuardVerdict(
            harmful=harmful,
            label="unsafe" if harmful else "safe",
            confidence=float(payload.get("confidence", 0.5)),
            category=leaf if harmful else None,
            reasoning=str(payload.get("reasoning", "")),
            meta={"backend": backend},
        )
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
        # Fail-safe: malformed model output escalates, never silently "safe".
        return GuardVerdict(
            harmful=True,
            label="escalate",
            confidence=None,
            category=None,
            reasoning=f"parse failure ({exc}); raw={raw_text[:200]!r}",
            meta={"backend": backend, "parse_error": True},
        )


class PromptedGuard:
    """A GuardModel backed by any chat-completions model. Providers differ only
    by model_call_fn(system_prompt, user_prompt) -> raw model text."""

    def __init__(self, model_call_fn: ModelCallFn, backend_name: str = "prompted",
                 rules: list | None = None, taxonomy: list[dict] | None = None):
        """`rules` makes this guard policy-driven: the org's rules are rendered
        into the system prompt, so the model is told what this org cares about
        instead of classifying against a fixed taxonomy and leaving the rules
        to gate the answer afterwards.

        rules=None reproduces the previous behaviour byte-for-byte — the same
        module-level SYSTEM_PROMPT and the same taxonomy leaf check — so every
        existing caller and every measured benchmark number is unaffected.
        """
        self._call = model_call_fn
        self._backend_name = backend_name
        self._rules = list(rules) if rules else None
        if self._rules:
            from sara_agent.guards.policy_prompt import allowed_leaves, build_system_prompt

            self._system = build_system_prompt(self._rules, taxonomy)
            self._allowed_leaves = allowed_leaves(self._rules, taxonomy)
        else:
            self._system = SYSTEM_PROMPT
            self._allowed_leaves = None

    @property
    def system_prompt(self) -> str:
        """Exposed so a caller can measure prompt size — policy-driven prompts
        grow with the rule count, and recall against a long policy is an open
        question (docs/policy_driven_sara_design.md §2(i))."""
        return self._system

    def classify(self, prompt: str, response: str | None = None) -> GuardVerdict:
        user_prompt = f"Message to classify:\n{prompt}"
        if response:
            user_prompt += f"\n\nModel's response to it:\n{response}"
        raw = self._call(self._system, user_prompt)
        return parse_verdict(raw, backend=self._backend_name,
                             allowed_leaves=self._allowed_leaves)


def _mock_call(canned: dict) -> ModelCallFn:
    def _fn(system_prompt: str, user_prompt: str) -> str:
        return f"<think>mock</think>\n<result>{json.dumps(canned)}</result>"
    return _fn


class MockPromptedGuard(PromptedGuard):
    """Deterministic, no network, no API key — for tests and CI."""

    def __init__(self, canned: dict | None = None):
        canned = canned or {"harmful": False, "leaf": None, "confidence": 0.1,
                             "reasoning": "mock: no attack indicators"}
        super().__init__(_mock_call(canned), backend_name="mock-prompted")


register("mock-prompted", lambda **cfg: MockPromptedGuard(**cfg))
