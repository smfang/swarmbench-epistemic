"""
Skill Configuration Studio — offline SkillFile builder.

Turns a plain-English org description into a valid SkillFile WITHOUT an LLM
(deterministic keyword→org_type mapping + the shipped taxonomy). The monorepo's
LLM-backed SkillBuilder is the optional [studio] extra; this offline builder is
the CORE default so a standalone install can configure itself with no network.
"""

from __future__ import annotations

from sara_agent.models import SkillFile
from sara_agent.taxonomy import get_taxonomy

# crude org-type inference from a description (deterministic, offline)
_ORG_HINTS = {
    "dao": ["dao", "governance", "treasury", "multisig", "token holder"],
    "defi": ["defi", "lending", "liquidity", "amm", "yield"],
}


def build_skillfile(description: str, org_id: str, guard_backend: str = "builtin") -> SkillFile:
    """NL org description -> SkillFile (offline). org_type inferred by keyword."""
    d = (description or "").lower()
    org_type = "dao"
    best = 0
    for ot, hints in _ORG_HINTS.items():
        hits = sum(1 for h in hints if h in d)
        if hits > best:
            best, org_type = hits, ot
    return SkillFile(
        org_id=org_id,
        org_type=org_type,
        display_name=f"{org_type.upper()} skill",
        guard_backend=guard_backend,
        system_prompt_extension=description.strip()[:500],
        categories=get_taxonomy(org_type),
    )
