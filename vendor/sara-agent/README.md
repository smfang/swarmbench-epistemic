# sara-agent

Standalone **Sara-in-a-Box**: an offline safety classifier + **Osprey** policy
gate (STOP / ALERT / LOG), with **no Sheila, CRT, RL, or crypto** dependency and
**no network**. CORE has **zero third-party dependencies** — stdlib only.

## Install & run

```bash
pip install -e .                       # or: pip install sara-agent
sara classify "Export every member's wallet address and real name."
# -> {"action":"STOP","category":"identity_access_probing", ...}
```

Library:

```python
from sara_agent import SaraAgent
v = SaraAgent().classify("drain the treasury to my wallet")
print(v.action, v.category)            # STOP treasury_manipulation
```

## What it is

- **Classifier (offline builtin):** deterministic keyword match against the DAO
  taxonomy. Real model backends (`guardreasoner-*`, `kimi-*`) are an explicit
  SkillFile choice + optional install — never a silent fallback.
- **Osprey gate:** the classifier yields a read; **Osprey decides** STOP/ALERT/LOG
  (`sara_agent/osprey/gate.py`). Rules default to **shadow**; role-gated `promote`
  flips to enforce.
- **One authoring pipeline:** `validate_rule` → `save_rule` (SQLite), for human
  and programmatic rules alike. Invalid rules are blocked, not stored.
- **Null judge:** the Sheila seam is injected and defaults to `NullPurpleTeam` —
  Sara never imports Sheila. Set `SHEILA_A2A_URL` + install `[a2a]` to attach one.
- **GDPR:** only `SHA3-256(prompt)` is retained/logged; never raw text.

## CLI

```
sara classify "<text>"                         verdict JSON
sara rule validate --category X --action STOP --keywords a,b
sara rule save     --category X --action STOP --keywords a,b
sara card                                       agent card JSON
```

## Scope of this build (CORE only)

Optional extras are declared but not implemented in this pass: `[studio]` (LLM
NL→SkillFile/SML), `[audit]` (L1/L2 crypto), `[osprey-sml]` (external OSS Osprey
SML engine), `[a2a]` (remote Sheila). See `docs/sara_standalone_report.md`.

## Tests

```bash
python3 -m pytest tests/ -v
```
