"""
WindowedGuard — makes any GuardModel session-aware.

THE PROBLEM IT SOLVES. Every guard in this package classifies ONE prompt
with no memory of the conversation. That is fine single-turn, and defeated
by construction multi-turn: an attacker who establishes the ask in turn 0
and then refers back to it anaphorically ("go ahead with that") produces
follow-up turns that are individually innocuous. A stateless guard re-reads
each turn cold, finds nothing, and clears a request it correctly refused
moments earlier. Measured on the shipped dataset: the builtin guard catches
18/18 attack seeds at turn 0, then clears them from turn 1 onward under
AnaphoricAttacker — a 0.00 -> 1.00 flip.

WHAT IT DOES. Two mechanisms, both keyed on the session's own history:

  1. STICKY DETECTION (defends flip rate). Once any turn in the window was
     independently harmful, the session stays flagged — the earlier verdict
     is carried forward rather than re-derived from the current turn alone.
     An attacker cannot launder a refused request by rephrasing it into
     something that looks clean in isolation.

  2. WINDOW AGGREGATION (defends signal-splitting). The concatenated window
     is also classified, catching an ask assembled across turns that no
     single turn carries. Strictly additive to (1).

WHAT IT DOES NOT DO. It cannot invent signal that is nowhere in the
conversation: an attack whose every turn — and whose concatenation — is
keyword-free is still missed by a keyword inner guard. Windowing changes
WHEN a guard can use evidence, not WHETHER the evidence exists.

WHY IT IS NOT A DROP-IN. `GuardModel.classify(prompt)` takes one prompt and
no session identifier, so a rolling internal buffer would interleave
unrelated sessions (run_multi_turn's loop is turn-major: case1-turn1,
case2-turn1, ...). History is therefore passed EXPLICITLY via
classify_history(). classify() remains a plain stateless passthrough so a
WindowedGuard is still a valid GuardModel for single-turn eval, where it is
exactly equivalent to its inner guard.
"""

from __future__ import annotations

from sara_agent.guards.base import GuardVerdict
from sara_agent.guards.registry import register

DEFAULT_WINDOW = 4


def _rank(label: str) -> int:
    # escalate outranks safe but not unsafe: an uncertain read should not
    # override a confident detection, nor be discarded as if it were clean.
    return {"safe": 0, "escalate": 1, "unsafe": 2}.get(label, 1)


class WindowedGuard:
    """Wraps any GuardModel. `window` is the number of most-recent turns
    considered; the turn-0 seed is ALWAYS included regardless of window, since
    it carries the session's original intent."""

    def __init__(self, inner, window: int = DEFAULT_WINDOW, aggregate: bool = True,
                 trajectory_rules: list | None = None):
        self._inner = inner
        self._window = max(1, int(window))
        self._aggregate = aggregate
        # Detections over the window that no per-turn classifier can make —
        # e.g. "N distinct sources queried, then joined". INJECTED rather
        # than built in: this class stays domain-free, and the scraping
        # notion of a "source" lives in the rule (see guards/trajectory.py).
        self._trajectory_rules = list(trajectory_rules or [])

    @property
    def inner(self):
        return self._inner

    def classify(self, prompt: str, response: str | None = None) -> GuardVerdict:
        """Stateless passthrough — identical to the inner guard. Keeps this a
        valid GuardModel so single-turn eval and the registry work unchanged."""
        return self._inner.classify(prompt, response)

    def classify_history(self, history: list[str]) -> GuardVerdict:
        """Classify the CURRENT turn (history[-1]) with the session's prior
        turns as context. Returns the inner guard's own verdict shape."""
        if not history:
            raise ValueError("classify_history requires a non-empty history")

        turns = self._window_turns(history)
        per_turn = [(t, self._inner.classify(t)) for t in turns]

        best_text, best = max(per_turn, key=lambda tv: _rank(tv[1].label))

        if self._aggregate and len(turns) > 1:
            joined = "\n".join(turns)
            agg = self._inner.classify(joined)
            if _rank(agg.label) > _rank(best.label):
                best_text, best = joined, agg

        # Trajectory rules see the whole window. A rule that fires is
        # returned directly rather than competing on label rank: it detected
        # something no per-turn read could, so a per-turn "unsafe" of equal
        # rank must not shadow it — the trajectory reasoning is the more
        # informative finding for an operator.
        for rule in self._trajectory_rules:
            traj = rule.evaluate(turns)
            if traj is not None and _rank(traj.label) >= _rank(best.label):
                return traj

        current = per_turn[-1][1]
        # Compare by RANK, not identity. max() resolves ties to the first
        # occurrence, so when the current turn merely TIES with an earlier
        # one, `best` is that earlier turn and an identity check
        # (`best is current`) reads as "the current turn was weaker". The
        # method then fabricated a "carried forward from an earlier turn"
        # verdict — substituting the earlier turn's category/confidence and
        # emitting a self-contradictory reasoning string that claimed the
        # carry-forward while also reporting the current turn at the same
        # label. Never unsafe (the severity floor held either way), but
        # misleading provenance for anyone auditing why a verdict fired.
        if _rank(current.label) >= _rank(best.label):
            return current  # current turn is already as strong as anything in the window

        carried_from_turn = turns.index(best_text) if best_text in turns else None
        return GuardVerdict(
            harmful=best.harmful,
            label=best.label,
            confidence=best.confidence,
            category=best.category,
            reasoning=(
                f"windowed: carried forward from an earlier turn in this session "
                f"({best.reasoning}); current turn alone read as "
                f"{current.label!r}"
            ),
            meta={
                **dict(getattr(best, "meta", {}) or {}),
                "windowed": True,
                "window": self._window,
                "carried_from_turn": carried_from_turn,
                "current_turn_label": current.label,
            },
        )

    def _window_turns(self, history: list[str]) -> list[str]:
        """Most-recent `window` turns, with the turn-0 seed always included."""
        recent = history[-self._window:]
        if history[0] not in recent:
            return [history[0], *recent]
        return recent


def _build(inner: str = "builtin", window: int = DEFAULT_WINDOW, **cfg) -> WindowedGuard:
    """Factory for the registry: `inner` names the guard to wrap. Imported
    lazily so registering this backend does not drag in every other
    backend's optional dependencies."""
    from sara_agent.guards.registry import get_guard
    return WindowedGuard(get_guard(inner, **cfg), window=window)


register("windowed", _build)
