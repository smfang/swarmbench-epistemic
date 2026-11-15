"""
Builtin offline classifier — the CORE default guard backend.

Deterministic keyword matching against the taxonomy leaves. NO network, NO model,
NO GPU. This is the monorepo classifier's keyword-fallback path
(src/sarabox/classifier.py) as a first-class, standalone backend, so the whole
harness runs offline by default.

Real model backends (guardreasoner-*, kimi-*) are an explicit SkillFile choice
and a separate optional install — not part of CORE. Selecting one without its
extra installed must give a clear message, never a silent fallback.
"""

from __future__ import annotations

from sara_agent.guards.base import GuardVerdict
from sara_agent.guards.registry import register
from sara_agent.taxonomy import DAO_TAXONOMY


class BuiltinKeywordGuard:
    """Matches a prompt against each leaf's keywords; the highest-severity hit wins."""

    def __init__(self, taxonomy: list[dict] | None = None):
        self._tax = taxonomy or DAO_TAXONOMY

    def classify(self, prompt: str, response: str | None = None) -> GuardVerdict:
        p = (prompt or "").lower()
        best = None
        for cat in self._tax:
            for kw in cat.get("keywords", []):
                if kw in p:
                    if best is None or _rank(cat["severity"]) > _rank(best["severity"]):
                        best = cat
                    break
        if best is None:
            return GuardVerdict(harmful=False, label="safe", confidence=0.1,
                                category=None, reasoning="no attack indicators",
                                meta={"backend": "builtin"})
        # confidence keyed off the leaf's own threshold (deterministic, offline)
        conf = max(0.6, float(best.get("threshold", 0.7)))
        return GuardVerdict(harmful=True, label="unsafe", confidence=conf,
                            category=best["id"],
                            reasoning=f"keyword match for leaf {best['id']}",
                            meta={"backend": "builtin"})


def _rank(sev: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(sev, 0)


register("builtin", lambda **cfg: BuiltinKeywordGuard(**cfg))
