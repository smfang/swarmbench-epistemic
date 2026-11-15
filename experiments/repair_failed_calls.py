"""Re-run only the failed calls in a kimi arm file and merge them back.

A failed call is not a verdict. The scorer reads `flag`, and a timeout leaves
it None, which `bool(None)` turns into "not flagged" — a silent conversion of
'we never asked' into 'the model saw nothing'. Repair, or drop the pair; never
score it.
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
import swarmbench_atif as sb  # noqa: E402
from sara_agent.guards.openai_compat import openai_chat_call_fn  # noqa: E402
from sara_agent.guards.prompted import PromptedGuard  # noqa: E402
from sara_agent.rulepacks import load_pack  # noqa: E402

SP = Path(sys.argv[1])
TARGET = Path(sys.argv[2])
MODEL = os.environ.get("KIMI_MODEL", "kimi-k2.6")
WORKERS = int(os.environ.get("KIMI_WORKERS", "3"))

rules = load_pack("swarmbench", R.ORG)
call = openai_chat_call_fn(MODEL, "https://api.moonshot.ai/v1/chat/completions",
                           api_key_env="MOONSHOT_API_KEY", max_tokens=6000,
                           temperature=1, timeout_s=420)
guard = PromptedGuard(call, backend_name=f"kimi:{MODEL}", rules=rules)

truth = {(t["probe"], t["scenario"], t["condition"]): t
         for t in (json.loads(l) for l in (SP / "truth.jsonl").read_text().splitlines())}
trace = {p.stem: json.loads(p.read_text()) for p in (SP / "traces").glob("*.json")}
rows = [json.loads(l) for l in TARGET.read_text().splitlines()]


def full_text(t):
    view = sb.monitor_view(trace[t["trajectory_id"]])
    return "\n".join(R.render(s) for s in view["steps"])


def redo(r, attempt=2):
    t = truth[(r["probe"], r["scenario"], r["condition"])]
    text = full_text(t)
    for i in range(attempt):
        t0 = time.perf_counter()
        try:
            gv = guard.classify(text)
            return {**r, "chars": len(text), "latency_s": round(time.perf_counter() - t0, 1),
                    "label": gv.label, "category": gv.category, "confidence": gv.confidence, "reasoning": gv.reasoning,
                    "flag": gv.label in ("unsafe", "borderline", "escalate"),
                    "error": None, "repaired": True}
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            time.sleep(5)
    return {**r, "error": err, "repaired": False}


bad = [r for r in rows if r["error"]]
print(f"repairing {len(bad)} failed calls on {MODEL} with {WORKERS} workers...")
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    fixed = list(ex.map(redo, bad))

by = {(r["probe"], r["scenario"], r["condition"]): r for r in rows}
for r in fixed:
    by[(r["probe"], r["scenario"], r["condition"])] = r
merged = list(by.values())
with open(TARGET, "w") as f:
    for r in merged:
        f.write(json.dumps(r) + "\n")

still = [r for r in merged if r["error"]]
print(f"  repaired {sum(1 for r in fixed if not r['error'])}/{len(bad)}; "
      f"{len(still)} still failing")
for r in still:
    print(f"   STILL BAD {r['probe']}-{r['scenario']}-{r['condition']}: {r['error'][:70]}")
