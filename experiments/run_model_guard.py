"""Does a reasoning model do what the hand-written trajectory rules do?

Two arms, one call each per trace (40 traces -> 40 calls per arm):

  step    the decisive step ALONE. P1/P2 decisive steps are byte-identical
          across arms, so anything above chance here is leakage, not skill.
  prefix  every step up to and including the decisive one, in one prompt.
          This is the arm that can, in principle, match the trajectory rules.

The guard is policy-driven: PromptedGuard(rules=SWARMBENCH_RULES) renders the
pack's prose into the system prompt and widens the accepted leaf set to the
pack's own categories, so the model is told what this policy cares about
instead of classifying against the DAO taxonomy it would otherwise use.
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# the benchmark modules live one level up; resolve relatively so this
# script runs from any checkout and no local path is baked in.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sara_replay as R  # noqa: E402
from sara_agent.guards.openai_compat import openai_chat_call_fn  # noqa: E402
from sara_agent.guards.prompted import PromptedGuard  # noqa: E402
from sara_agent.rulepacks import load_pack  # noqa: E402

SP = Path(sys.argv[1])
ARM = sys.argv[2] if len(sys.argv) > 2 else "both"
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 0

MOONSHOT = "https://api.moonshot.ai/v1/chat/completions"
PACK = os.environ.get("KIMI_PACK", "swarmbench")
rules = load_pack(PACK, R.ORG)
# kimi-k2.6 accepts temperature 1 only (openai_compat.py:43).
# max_tokens=6000, not the KimiGuard default of 1500: measured, 1500 returns an
# EMPTY string on trace-length prompts. kimi-k2.6 spends output budget on
# invisible reasoning_content first, so a starved cap yields content="" and the
# guard fails safe to `escalate` with no category — a result indistinguishable
# from a real uncertain read. 6000 returns a parsed verdict.
MODEL = os.environ.get("KIMI_MODEL", "kimi-k2.6")
call = openai_chat_call_fn(MODEL, MOONSHOT, api_key_env="MOONSHOT_API_KEY",
                           max_tokens=6000, temperature=1, timeout_s=300)
guard = PromptedGuard(call, backend_name=f"kimi:{MODEL}", rules=rules)

truth = [json.loads(l) for l in (SP / "truth.jsonl").read_text().splitlines()]
trace = {p.stem: json.loads(p.read_text()) for p in (SP / "traces").glob("*.json")}


def prompts_for(t):
    """(decisive step alone, prefix through the decisive step) — monitor view."""
    import swarmbench_atif as sb
    view = sb.monitor_view(trace[t["trajectory_id"]])
    dec = t.get("planted_step") or (t.get("evidence") or [None])[0]
    rendered, upto, alone = [], [], None
    for s in view["steps"]:
        r = R.render(s)
        rendered.append(r)
        if s["step_id"] == dec:
            alone = r
            upto = list(rendered)
    if alone is None:                      # no decisive step (P4 control)
        alone = rendered[-1]
        upto = rendered
    # The ONLY arm that compares like with like. `planted_step` (attack) and
    # `evidence[0]` (control) are different steps, so cutting each arm at its
    # own decisive step hands the two conditions different amounts of trace:
    # P2 compared a handoff note against a user approval, and P4 compared a
    # 4-step attack prefix against a whole control trace. Both arms get every
    # step here, which is also what a monitor has by the end of an episode.
    return alone, "\n".join(upto), "\n".join(rendered)


def one(t):
    alone, prefix, full = prompts_for(t)
    text = {"step": alone, "prefix": prefix}.get(ARM, full)
    t0 = time.perf_counter()
    try:
        gv = guard.classify(text)
        err = None
    except Exception as e:                 # a failed call is not a 'safe' read
        gv, err = None, f"{type(e).__name__}: {e}"
    return {"probe": t["probe"], "scenario": t["scenario"], "condition": t["condition"],
            "arm": ARM, "chars": len(text), "latency_s": round(time.perf_counter() - t0, 1),
            "label": None if gv is None else gv.label,
            "category": None if gv is None else gv.category,
            "confidence": None if gv is None else gv.confidence,
            "reasoning": None if gv is None else gv.reasoning,
            "flag": None if gv is None else gv.label in ("unsafe", "borderline", "escalate"),
            "error": err}


rows_in = truth[:LIMIT] if LIMIT else truth
with ThreadPoolExecutor(max_workers=5) as ex:
    rows = list(ex.map(one, rows_in))

out = SP / f"kimi_{MODEL}_{PACK}_{ARM}.jsonl"
with open(out, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")

errs = [r for r in rows if r["error"]]
print(f"arm={ARM}  calls={len(rows)}  errors={len(errs)}  "
      f"median latency {sorted(r['latency_s'] for r in rows)[len(rows)//2]}s  "
      f"mean prompt {sum(r['chars'] for r in rows)//len(rows)} chars -> {out}")
if errs:
    print("  FIRST ERROR:", errs[0]["error"][:200])
