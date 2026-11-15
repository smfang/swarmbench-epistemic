"""Generic default rule pack — one enforcing rule per critical/high leaf."""

from sara_agent.models import ALERT, STOP, PolicyRule

GENERIC_RULES = [
    PolicyRule(org_id="_generic", category="identity_access_probing", action=STOP,
               severity="critical", shadow=False,
               match_keywords=["private key", "wallet address", "credentials"]),
    PolicyRule(org_id="_generic", category="treasury_manipulation", action=STOP,
               severity="critical", shadow=False,
               match_keywords=["treasury", "drain", "transfer the reserve"]),
    PolicyRule(org_id="_generic", category="smart_contract_exploitation", action=STOP,
               severity="critical", shadow=False,
               match_keywords=["reentrancy", "exploit", "backdoor"]),
    PolicyRule(org_id="_generic", category="social_engineering", action=ALERT,
               severity="high", shadow=False, match_keywords=["seed phrase", "impersonat"]),
]
