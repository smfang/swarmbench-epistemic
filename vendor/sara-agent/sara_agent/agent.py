"""
SaraAgent — the standalone library entry point.

`SaraAgent().classify(prompt) -> Verdict`: classify offline with the builtin
guard, then let Osprey gate the read into STOP / ALERT / LOG. The Sheila judge is
injected and defaults to NullPurpleTeam — Sara never imports Sheila.

GDPR: only SHA3-256(prompt) is retained on the Verdict / logged; raw prompt text
is never persisted or logged at level >= INFO.
"""

from __future__ import annotations

import hashlib
import logging

from sara_agent.guards import get_guard
from sara_agent.models import SkillFile, Verdict
from sara_agent.osprey.store import RuleStore
from sara_agent.osprey.gate import decide
from sara_agent.purpleteam import NullPurpleTeam, PurpleTeam
from sara_agent.rulepacks import load_pack

logger = logging.getLogger("sara_agent")


def sha3(prompt: str) -> str:
    return hashlib.sha3_256((prompt or "").encode()).hexdigest()


class SaraAgent:
    def __init__(
        self,
        skill: SkillFile | None = None,
        store: RuleStore | None = None,
        judge: PurpleTeam | None = None,
        org_id: str = "default",
        rulepack: str = "dao",
    ):
        self.skill = skill or SkillFile(org_id=org_id, org_type="dao",
                                        display_name="default", guard_backend="builtin")
        self.org_id = self.skill.org_id
        self.store = store or RuleStore()          # in-memory by default
        self.judge = judge or NullPurpleTeam()     # never Sheila unless injected
        self._guard = get_guard(self.skill.guard_backend)
        # seed the store with a rule pack if it's empty (so classify gates sensibly)
        if not self.store.list_rules_for_org(self.org_id):
            for r in load_pack(rulepack, self.org_id):
                self.store.save_rule(r)

    def classify(self, prompt: str, response: str | None = None) -> Verdict:
        digest = sha3(prompt)
        guard_verdict = self._guard.classify(prompt, response)
        rules = self.store.list_rules_for_org(self.org_id)
        verdict = decide(digest, prompt, guard_verdict, rules)
        # GDPR: log only the hash + outcome, never the raw prompt.
        logger.info("classify sha3=%s action=%s category=%s",
                    digest[:16], verdict.action, verdict.category)
        return verdict
