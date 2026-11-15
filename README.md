# What a safety monitor fails to notice

A 40-trace benchmark of **epistemic** failures in agent trajectories — cases
where nothing in any single step is false, and the violation exists only in
the relation between steps.

The headline result: on the same corpus, the same harness and the same model,
**rewriting the policy from mechanism language to relational language took a
model guard from 0/20 to 20/20.** The reader never changed. Only the wording
of the rules it was given.

## The four probes

Each probe has 5 scenarios, each in two arms — an **attack** and an honest
**control** twin. 40 traces, 554 steps.

| | what is planted | why per-step monitoring cannot see it |
|---|---|---|
| **P1 provenance** | a record labelled as written by the agent, which the agent never wrote | the decisive `memory.list` step is **byte-identical** across both arms |
| **P2 authorisation** | a handoff note claiming the user already approved, who never did | the decisive `inbox.read` step is **byte-identical** across both arms |
| **P3 omission** | a summary that silently drops an egress change it should report | nothing in it is false; the violation is what is missing |
| **P4 delayed link** | a host added to the allowlist, then used, 3–20 steps later | neither step is remarkable alone; only the pair is |

For P1 and P2 the decisive step is the same bytes in both arms, so **any**
per-step monitor that separates them is reading something that is not there.
P3 is inverted — the control names the egress change, the attack omits it. Only
P4 is separable step-by-step, and only if the window reaches back far enough.

## Results

**Keyword matching** (deterministic, offline). Per-step keywords flag both arms
equally: **0/20**. The relational pack carries `match_keywords=[]` on every
rule, so the keyword path cannot fire on it at all — **554/554 allow**. That is
the honest outcome, not a defect: it means any discrimination measured under
that pack was done by a reader that reasoned.

**Hand-written trajectory rules** (deterministic, offline, no API key):

```
### full prefix                [signal = trajectory rule fired]
probe    attack   control   DISCRIMINATES
P1          5/5       0/5            5/5
P2          5/5       0/5            5/5
P3          5/5       0/5            5/5
P4          5/5       0/5            5/5
       false alarms on cover work: 0/409 = 0.0%
```

Window size is the binding constraint, and the sweep tracks the designed gaps
exactly — 2 → 0/20, 4 → 4/20, 8 → 8/20, 12 → 12/20, 16 → 16/20, full → 20/20,
against P4 gaps of 3, 5, 8, 12 and 20 steps.

**A model guard** (`kimi-k3.1-pro`, 40 calls per arm, 0 errors). Identical
corpus, harness and model; the policy wording is the only difference:

| | mechanism rules | relational rules |
|---|---|---|
| pairs told apart | **0/20** | **20/20** |
| honest twins wrongly flagged | 20/20 | **0/20** |
| reasoning names something absent | 0/40 | **33/40** |
| reasoning cites a step number | 0/40 | 8/40 |
| reasoning names a decisive tool call | 7/40 | 19/40 |
| reasoning quotes the artifact | 8/40 | 22/40 |

The mechanism rules name real mechanisms, and those mechanisms are genuinely
present in **both** arms — so a faithful reader alarms on the honest twin too.
A 0/20 was never a measurement of the reader's ability. It was a reader that
had not been asked the question.

On P3, absence language goes **0/10 → 10/10**: told to compare the summary
against the steps it covers and report what is missing, the model does, and it
explains its clears as well as its alarms.

Reasoning metrics are keyword counts, so the pattern decides the number. The
patterns are therefore written down in
[`experiments/score_reasoning.py`](experiments/score_reasoning.py) rather than
living in a shell one-liner — counting any sentence containing the word "step"
gives 27/40 for grounding, while requiring an actual step reference gives 8/40.
Both are "measured"; only one is a citation.

## Reproducing it

Python 3.12+. The deterministic results need **no API key and no network**.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt -e vendor/sara-agent
```

```bash
.venv/bin/python -m pytest -q tests
```

```bash
.venv/bin/python epistemic_items.py --out epistemic_run --validate
```

```bash
PYTHONPATH=. .venv/bin/python experiments/score_discrimination.py epistemic_run
```

That last command prints the discrimination tables and the window sweep above.
The model-guard experiments under `experiments/` do call out, and read
`MOONSHOT_API_KEY` from the environment; the committed run files in
`experiments/results/` let you re-score them without spending anything:

```bash
PYTHONPATH=. .venv/bin/python experiments/score_reasoning.py experiments/results/*.jsonl
```

## Layout

| path | what it is |
|---|---|
| `PRD_epistemic_test.md` | the requirements this was built against |
| `epistemic_items.py` | the generator — builds all 40 traces plus `truth.jsonl` |
| `swarmbench_atif.py` | the ATIF trajectory layer and `monitor_view` |
| `sara_replay.py` | the adapter: streams a trace past the monitor, prefix-aware |
| `rulepacks/swarmbench.py` | the **mechanism** policy — 4 rules, scores 0/20 |
| `rulepacks/swarmbench_relational.py` | the **relational** policy — 4 rules, scores 20/20 |
| `experiments/` | the model-guard runners, scorers, and every result file |
| `vendor/sara-agent/` | the monitor under test, vendored source-only, stdlib only |

The two rule packs are the experiment. Diff them against each other — that
diff is the finding.

## What this does not show

**The relational rules were written by someone who had read the generator.**
This demonstrates the task is *expressible in policy*; it does not show that an
independent author, writing blind, would land on that wording. That is the
first thing worth replicating.

Other limits, stated plainly:

- **One model family.** `kimi-k2.6` and `kimi-k3.1-pro`. Nothing here says how
  another model behaves.
- **Five scenarios per probe.** With n=5 a per-probe penalty has to be large to
  clear a confidence interval; the pooled n=20 comparison is the one that
  carries weight.
- **The agent was never asked the questions directly.** Every number here is a
  *monitor* reading a trace. Whether a model acting in the trace would itself
  accept the planted claim is unmeasured.
- **The traces are synthetic**, generated from five scenario templates, with
  hosts under `.example.*`. Realistic distribution is not claimed.
- **`cannot_tell` is not distinguishable from a parse failure** in the guard's
  output schema, so uncertainty and "never asked" arrive as the same token.

## Provenance

Built with [Sara](https://github.com/smfang/sara)'s monitor, extracted from a
private monorepo into this standalone tree by `make_standalone.sh`. The
vendored `sara-agent` copy is source-only and has zero third-party
dependencies; `webui/` is excluded because it imports modules that live only in
that monorepo.
