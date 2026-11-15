"""
The Osprey gate — verdict -> STOP / ALERT / LOG.

This is the load-bearing invariant (spec guardrail): the classifier yields a
read (leaf + confidence); OSPREY decides the action. Mirrors the monorepo
SaraPolicyMonitor.evaluate (src/osprey_ui/monitor.py): iterate the org's rules,
pick the highest-severity match, apply shadow suppression for STOP.

Pure Python, offline. The external OSS Osprey SML engine is an optional
production upgrade ([osprey-sml] extra); this is the built-in fallback that
already exists in the platform.
"""

from __future__ import annotations

from sara_agent.guards.base import GuardVerdict
from sara_agent.models import LOG, STOP, PolicyRule, Verdict, severity_rank


def _rule_matches(rule: PolicyRule, prompt_lower: str, guard: GuardVerdict) -> bool:
    """A rule matches if the classifier tagged its category with enough
    confidence, or a keyword hits.

    The confidence gate on the category path is what this function was
    missing. It previously fired on ANY category match at ANY confidence, so
    the builtin guard tagging "What is the treasury balance?" as
    treasury_manipulation at 0.6 produced a STOP on a read-only query. The
    monorepo's equivalent (src/osprey_ui/monitor.py) has always respected a
    threshold; this had diverged.

    `confidence_threshold` defaults to 0.0, so a rulepack that does not set
    it behaves exactly as before.
    """
    if guard.category and guard.category == rule.category:
        threshold = getattr(rule, "confidence_threshold", 0.0) or 0.0
        if (guard.confidence if guard.confidence is not None else 1.0) >= threshold:
            return True
    return any(kw.lower() in prompt_lower for kw in rule.match_keywords)


def decide(prompt_sha3: str, prompt: str, guard: GuardVerdict,
           rules: list[PolicyRule]) -> Verdict:
    """Apply the ruleset to a classifier verdict and return the gated Verdict.

    Osprey owns the action. No rule match -> LOG. Highest-severity matching rule
    wins. A STOP rule still in shadow is recorded but downgraded to LOG (logged,
    not enforced) with shadowed=True.
    """
    p = (prompt or "").lower()
    matched: PolicyRule | None = None
    for rule in rules:
        if _rule_matches(rule, p, guard):
            if matched is None or severity_rank(rule.severity) > severity_rank(matched.severity):
                matched = rule

    if matched is None:
        return Verdict(prompt_sha3=prompt_sha3, label=guard.label,
                       category=guard.category, confidence=guard.confidence or 0.0,
                       action=LOG, matched_rule_id=None, shadowed=False,
                       reasoning="no policy rule matched")

    action = matched.action
    shadowed = False
    if action == STOP and matched.shadow:
        action = LOG          # shadow: record, do not enforce
        shadowed = True

    return Verdict(
        prompt_sha3=prompt_sha3, label=guard.label, category=guard.category,
        confidence=guard.confidence or 0.0, action=action,
        matched_rule_id=matched.rule_id, shadowed=shadowed,
        reasoning=f"rule {matched.rule_id} ({matched.action}"
                  f"{', shadowed' if shadowed else ''})",
    )
