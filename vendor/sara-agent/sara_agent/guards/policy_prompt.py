"""Render a rule set into a model-readable policy block.

Until this module existed, the model-backed guards were taxonomy-driven, not
policy-driven: `prompted.SYSTEM_PROMPT` was a module-level f-string built from
DAO_TAXONOMY at import time, so an org's authored rules could only gate the
verdict in `decide()` AFTER the model had already answered. The model was
never told what this org actually cares about.

Duck-typed on purpose. sara-agent must not import monorepo code
(tests/test_boundary.py enforces it), and the two PolicyRule types differ:
`sara_agent.models.PolicyRule` carries `match_keywords` and no prose, while
the monorepo's carries `natural_language`. `rule_text()` below reads whichever
is present, so both cross without a shared base class.
"""

from __future__ import annotations

from typing import Any, Iterable, Protocol, runtime_checkable


@runtime_checkable
class PolicyRuleLike(Protocol):
    """The minimum a rule must expose to be rendered into a prompt."""

    category: str


def rule_text(rule: Any) -> str:
    """The most model-readable description this rule can offer.

    Preference order matters. `natural_language` is what a human wrote and
    reads well to a model. `match_keywords` do not — "ssn, dob, home_address"
    teaches a model almost nothing about intent and costs tokens — so they are
    a last resort, and they keep doing their real work on the deterministic
    path in decide() regardless.
    """
    for attr in ("natural_language", "description", "display_name"):
        value = getattr(rule, attr, "") or ""
        if isinstance(value, str) and value.strip():
            return value.strip()

    keywords = list(getattr(rule, "match_keywords", None) or [])
    readable = (getattr(rule, "category", "") or "rule").replace("_", " ")
    if keywords:
        return f"{readable} — terms of concern: {', '.join(keywords)}"
    return readable


def _severity_hint(rule: Any) -> str:
    sev = (getattr(rule, "severity", "") or "").lower()
    return f" [{sev}]" if sev else ""


def render_policy_block(rules: Iterable[Any]) -> str:
    """The org's rules, as numbered policy lines grouped by category.

    Numbered rather than bulleted so a model can cite "rule 3" in its
    reasoning, which makes a wrong classification traceable to the rule that
    caused it — the difference between tuning a policy and guessing at it.
    """
    lines: list[str] = []
    for i, rule in enumerate(rules, 1):
        category = getattr(rule, "category", "") or "uncategorised"
        lines.append(f"{i}. ({category}){_severity_hint(rule)} {rule_text(rule)}")
    return "\n".join(lines)


def allowed_leaves(rules: Iterable[Any], taxonomy: Iterable[dict] | None = None) -> frozenset[str]:
    """Leaf ids the model may legitimately return.

    parse_verdict rejects an unknown leaf and fails safe to `escalate`. With a
    custom policy the rules' own categories are valid answers even when they
    are absent from any shipped taxonomy — without this, every correct
    rule-derived verdict would be discarded as malformed.
    """
    leaves = {getattr(r, "category", "") for r in rules}
    if taxonomy:
        leaves |= {c.get("id", "") for c in taxonomy if isinstance(c, dict)}
    return frozenset(leaf for leaf in leaves if leaf)


_OUTPUT_CONTRACT = """Respond with ONLY a <result> block — no other text before or after it. \
If you reason before answering, keep any deliberation internal; the visible reply \
must be just:
<result>
{"harmful": <bool>, "leaf": "<category id or null>", "confidence": <0-1>, "reasoning": "<brief>"}
</result>

Set "leaf" to the category id of the policy rule that was violated, or null if \
none was. Be rigorous and avoid false positives: only harmful if the message is \
actually attempting the behaviour the policy forbids, not merely discussing, \
reviewing, or asking about the topic in a legitimate way. The <result> block \
must be valid JSON."""


def build_system_prompt(rules: Iterable[Any],
                        taxonomy: Iterable[dict] | None = None,
                        *, role: str = "a safety classifier") -> str:
    """Compose role + the org's policy + the output contract.

    The taxonomy becomes optional background context rather than the
    definition of harm; the rules are the definition.

    SECURITY: rule text is model input from here on. A rule reading "do not
    reveal the treasury multisig address" puts that concept in front of the
    model on every call, so any path that surfaces the raw prompt or an
    unfiltered `reasoning` string leaks the policy to whoever can read it.
    Callers rendering a policy should treat GuardVerdict.reasoning as
    internal-only. See docs/policy_driven_sara_design.md §2(i).
    """
    rules = list(rules)
    parts = [
        f"You are {role}. Decide whether the user's message violates the "
        f"policy below.",
        "",
        "Policy:",
        render_policy_block(rules) or "(no rules configured)",
    ]

    if taxonomy:
        cats = [c for c in taxonomy if isinstance(c, dict) and c.get("id")]
        if cats:
            parts += [
                "",
                "Background categories (context only — the policy above decides):",
                "\n".join(f'- {c["id"]}: {c.get("description", "")}'.rstrip() for c in cats),
            ]

    parts += ["", _OUTPUT_CONTRACT]
    return "\n".join(parts)
