"""
`sara` CLI — offline classification + rule authoring.

    sara classify "<text>"                         -> verdict JSON
    sara rule validate --category X --action STOP --keywords a,b
    sara rule save     --category X --action STOP --keywords a,b [--org O]
    sara card                                       -> agent card JSON

No network, no Sheila. Uses the builtin guard + the DAO rule pack by default.
"""

from __future__ import annotations

import argparse
import json
import sys

from sara_agent.agent import SaraAgent
from sara_agent.models import PolicyRule
from sara_agent.osprey.authoring import save_rule, validate_rule


def _classify(args) -> int:
    agent = SaraAgent(org_id=args.org, rulepack=args.rulepack)
    verdict = agent.classify(args.text)
    print(json.dumps(verdict.to_dict(), indent=2))
    return 0


def _rule(args) -> int:
    rule = PolicyRule(
        org_id=args.org, category=args.category, action=args.action.upper(),
        severity=args.severity,
        match_keywords=[k.strip() for k in (args.keywords or "").split(",") if k.strip()],
    )
    if args.rule_cmd == "validate":
        errors = validate_rule(rule)
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return 0 if not errors else 1
    if args.rule_cmd == "save":
        agent = SaraAgent(org_id=args.org, rulepack=args.rulepack)
        try:
            saved = save_rule(agent.store, rule, author=args.author)
        except ValueError as exc:
            print(json.dumps({"saved": False, "error": str(exc)}, indent=2))
            return 1
        print(json.dumps({"saved": True, "rule": saved.to_dict()}, indent=2))
        return 0
    return 2


def _card(args) -> int:
    card = {
        "name": "sara", "role": "safety-classifier",
        "capabilities": ["classify", "rule-authoring"],
        "guard_backend": "builtin", "gate": "osprey",
        "offline": True, "judge": "null (Sheila optional via SHEILA_A2A_URL)",
    }
    print(json.dumps(card, indent=2))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="sara", description=__doc__)
    p.add_argument("--org", default="default")
    p.add_argument("--rulepack", default="dao")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("classify", help="classify a prompt")
    c.add_argument("text")
    c.set_defaults(func=_classify)

    r = sub.add_parser("rule", help="author a policy rule")
    r.add_argument("rule_cmd", choices=["validate", "save", "preview", "promote"])
    r.add_argument("--category", default="")
    r.add_argument("--action", default="ALERT")
    r.add_argument("--severity", default="high")
    r.add_argument("--keywords", default="")
    r.add_argument("--author", default="cli")
    r.set_defaults(func=_rule)

    cd = sub.add_parser("card", help="print the agent card")
    cd.set_defaults(func=_card)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
