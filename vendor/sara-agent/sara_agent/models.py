"""
Core domain models — stdlib dataclasses only (no pydantic, no third-party deps).

Mirrors the shapes of the monorepo's SkillFile / PolicyRule / ClassificationResult
closely enough for the standalone gate + authoring path, without dragging in the
platform's pydantic/ClickHouse stack.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

# Gate actions, in ascending severity. Osprey decides which one fires.
LOG = "LOG"
ALERT = "ALERT"
STOP = "STOP"
ACTIONS = (LOG, ALERT, STOP)
_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass
class SkillFile:
    """An org's configuration: it selects the classifier backend AND the ruleset."""
    org_id: str
    org_type: str = "dao"
    display_name: str = ""
    guard_backend: str = "builtin"          # name resolved via guards.registry
    system_prompt_extension: str = ""
    categories: list[dict] = field(default_factory=list)
    skill_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PolicyRule:
    """One Osprey policy rule. Matches on a taxonomy leaf (category) and/or
    keywords; carries the gate action + shadow flag + an audit trail."""
    org_id: str
    category: str                            # taxonomy leaf id this rule tags
    action: str = ALERT                      # LOG | ALERT | STOP
    severity: str = "high"
    match_keywords: list[str] = field(default_factory=list)
    #: The rule in prose — what it forbids, and what it deliberately does not.
    #:
    #: Keywords are for the deterministic path. This is what a MODEL reasons
    #: over: policy_prompt.rule_text() prefers it, and a Jev question derives
    #: its instructions from it. Without prose, a rule renders as its category
    #: name plus its keyword list, so two "independent" model layers given
    #: the same rulepack are really reading the same word list — and their
    #: agreement stops being evidence of anything.
    #:
    #: Say what is NOT covered as well as what is. "Reading a balance is not
    #: covered" is the sentence that prevents a false positive.
    description: str = ""
    #: Minimum classifier confidence before the CATEGORY path fires this rule.
    #:
    #: Without it, _rule_matches returned True whenever the guard tagged the
    #: rule's category at ANY confidence. Measured: the builtin guard labels
    #: "What is the treasury balance?" as treasury_manipulation at 0.6, which
    #: fired a STOP on a read-only balance query. The monorepo's equivalent
    #: matcher (src/osprey_ui/monitor.py) has always gated this path on a
    #: threshold; sara_agent's had diverged.
    #:
    #: 0.0 keeps the previous behaviour, so every existing rulepack and every
    #: measured benchmark number is unaffected until a pack opts in.
    confidence_threshold: float = 0.0
    osprey_sml: str = ""                     # raw SML (optional; informational in CORE)
    shadow: bool = True                      # new rules default to shadow (no enforce)
    rule_id: str = field(default_factory=lambda: "rule_" + uuid.uuid4().hex[:12])
    # audit-on-save (link 12): author + timestamp + version
    author: str = "system"
    version: int = 1
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Verdict:
    """The end-to-end result: the classifier's read + Osprey's gate decision."""
    prompt_sha3: str                         # GDPR: never the raw prompt
    label: str                               # "unsafe" | "safe" | "borderline"
    category: Optional[str]
    confidence: float
    action: str                              # LOG | ALERT | STOP (Osprey's decision)
    matched_rule_id: Optional[str]
    shadowed: bool                           # True if a STOP was suppressed (shadow)
    reasoning: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def severity_rank(sev: str) -> int:
    return _SEVERITY_RANK.get(sev, 0)
