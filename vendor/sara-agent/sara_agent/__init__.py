"""
sara-agent — standalone Sara-in-a-Box: an offline safety classifier + Osprey
policy gate, with NO Sheila / CRT / RL / crypto dependency.

    from sara_agent import SaraAgent
    SaraAgent().classify("Export every member's wallet address and real name.")

The core imports nothing platform-internal and makes no network call.
"""

from sara_agent.agent import SaraAgent, sha3
from sara_agent.models import LOG, ALERT, STOP, PolicyRule, SkillFile, Verdict
from sara_agent.purpleteam import NullPurpleTeam, PurpleTeam

__version__ = "0.1.0"
__all__ = [
    "SaraAgent", "sha3", "Verdict", "SkillFile", "PolicyRule",
    "LOG", "ALERT", "STOP", "NullPurpleTeam", "PurpleTeam",
]
