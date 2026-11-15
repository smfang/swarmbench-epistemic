"""Shipped rule packs: a generic default + a DAO example. Every rule is tagged to
a real taxonomy leaf."""
from sara_agent.rulepacks.dao import DAO_RULES
from sara_agent.rulepacks.generic import GENERIC_RULES
from sara_agent.rulepacks.scraping import SCRAPING_RULES
from sara_agent.rulepacks.swarmbench import SWARMBENCH_RULES
from sara_agent.rulepacks.swarmbench_relational import SWARMBENCH_RELATIONAL_RULES

PACKS = {"generic": GENERIC_RULES, "dao": DAO_RULES, "scraping": SCRAPING_RULES,
         "swarmbench": SWARMBENCH_RULES,
         "swarmbench_rel": SWARMBENCH_RELATIONAL_RULES}


def load_pack(name: str, org_id: str):
    """Return copies of a pack's rules bound to org_id (so saved rules are org-scoped)."""
    from dataclasses import replace
    if name not in PACKS:
        raise KeyError(f"unknown rule pack {name!r}. Available: {sorted(PACKS)}")
    return [replace(r, org_id=org_id) for r in PACKS[name]]
