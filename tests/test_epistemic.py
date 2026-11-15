"""End-to-end checks for the epistemic test: generate, self-check, simulate, score."""
import json

import epistemic_items as ei
import score_epistemic as se
import swarmbench_atif as sb


def test_generator_self_check_passes():
    items, truths, traces = ei.build(seed=7)
    assert ei.self_check(items, truths, traces) == []
    assert len(items) == 40


def test_generator_is_deterministic():
    a = ei.build(seed=7)[0]
    b = ei.build(seed=7)[0]
    assert json.dumps(a) == json.dumps(b)


def test_model_input_has_no_labels_or_giveaways():
    items, _, _ = ei.build(seed=7)
    for it in items:
        assert not sb._has_ns_key(it["trace"])
        text = json.dumps(it).lower()
        for w in ("attack", "control", "planted", "trap", "swarmbench"):
            assert w not in text, (it["item_id"], w)


def test_scorer_separates_credulous_from_careful(tmp_path):
    items, truths, _ = ei.build(seed=7)
    (tmp_path / "truth.jsonl").write_text("\n".join(json.dumps(t) for t in truths) + "\n")
    se.simulate(tmp_path)
    res = se.score(tmp_path)
    assert res["credulous"]["attack_accuracy"][0] < res["careful"]["attack_accuracy"][0]
    assert res["credulous"]["brier"] > res["careful"]["brier"]
    assert "sara_catch_on_model_errors" in res["careful"]


def test_parse_raw_model_text():
    row = {"raw": 'Sure.\n{"answer": "Unknown", "evidence_step_ids": ["4", 7], "verified": "cannot_tell", "confidence": 1.4}'}
    a = se.parse_answer(row)
    assert a["answer"] == "unknown" and a["evidence"] == [4, 7] and a["confidence"] == 1.0
