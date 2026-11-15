"""
The ONE shared rule-authoring pipeline (link 6: no side door).

Both human-authored and programmatic rules go through validate_rule -> save_rule
here. Mirrors the monorepo's single validate/save path (src/osprey_ui/server.py).
`promote` flips a shadow rule to enforcing (link 9), gated by an authorized role.

validate is deterministic/model-free (the CORE path); an LLM NL->SML compiler is
the optional [studio] extra, not part of CORE.
"""

from __future__ import annotations

from sara_agent.models import ACTIONS, PolicyRule, severity_rank
from sara_agent.osprey.store import RuleStore
from sara_agent.taxonomy import is_valid_leaf

_VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def validate_rule(rule: PolicyRule) -> list[str]:
    """Deterministic schema validation. Returns a list of errors ([] == valid)."""
    errors: list[str] = []
    if not rule.org_id:
        errors.append("org_id is required")
    if rule.action not in ACTIONS:
        errors.append(f"action must be one of {sorted(ACTIONS)}, got {rule.action!r}")
    if rule.severity not in _VALID_SEVERITIES:
        errors.append(f"severity must be one of {sorted(_VALID_SEVERITIES)}")
    if not is_valid_leaf(rule.category) or rule.category is None:
        errors.append(f"category must be a real taxonomy leaf, got {rule.category!r}")
    if not rule.match_keywords and not rule.category:
        errors.append("rule must match on a category or at least one keyword")
    return errors


def save_rule(store: RuleStore, rule: PolicyRule, author: str = "human") -> PolicyRule:
    """The single save pipeline: validate -> stamp audit -> persist.

    Raises ValueError if invalid — an invalid rule is BLOCKED, never stored
    (link 5 gates link 6). New rules default to shadow (link 9)."""
    errors = validate_rule(rule)
    if errors:
        raise ValueError("rule validation failed: " + "; ".join(errors))
    rule.author = author           # audit-on-save (link 12)
    store.save_rule(rule)          # store bumps version on update
    return rule


def promote_rule(store: RuleStore, rule_id: str, role: str) -> PolicyRule:
    """Flip a shadow rule to enforcing (link 9). Role-gated: only 'admin' may promote."""
    if role != "admin":
        raise PermissionError(f"role {role!r} may not promote rules (requires 'admin')")
    rule = store.get_rule(rule_id)
    if rule is None:
        raise KeyError(f"unknown rule {rule_id!r}")
    rule.shadow = False
    store.save_rule(rule)          # re-save through the store (version bumps)
    return rule
