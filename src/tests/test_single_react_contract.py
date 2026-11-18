import json
from pathlib import Path

import pytest

from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.schemas import make_run_id
from lab8.shapes import single


@pytest.mark.parametrize(
    ("choice", "expected_tool"),
    [("single_decide:0", "compute_compensation"), ("single_decide:1", "lookup_policy")],
)
def test_single_model_choice_preserves_the_quote(
    public_db, monkeypatch, tmp_path, choice, expected_tool
):
    monkeypatch.chdir(tmp_path)
    marker = "CANARY_SECRET_SINGLE_TICKET"
    conn = connect(public_db)
    try:
        conn.execute("UPDATE claims SET ticket = ? WHERE claim_id = 'C-014'", (marker,))
        conn.commit()
    finally:
        conn.close()

    complete = single.complete

    def choose(budget, *, seed, purpose, prompt):
        assert marker not in prompt
        complete(budget, seed=seed, purpose=purpose, prompt=prompt)
        return choice

    monkeypatch.setattr(single, "complete", choose)
    result = single.run_claim("C-014", seed=11, store_path=str(public_db))
    assert result.status == "resolved"
    assert result.proposal_amount == 150000
    assert result.refund_effects[0]["amount_vnd"] == 120000
    assert (result.model_calls, result.tool_calls) == (1, 3)

    trace_text = Path(result.trace_path).read_text(encoding="utf-8")
    events = json.loads(trace_text)["events"]
    choices = [event["payload"]["tool"] for event in events if event["kind"] == "agent_choice"]
    assert choices == [expected_tool]
    assert marker not in trace_text


@pytest.mark.parametrize(
    "point", ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"]
)
def test_single_writes_trace_before_crash(public_db, monkeypatch, tmp_path, point):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(InjectedCrash, match=point):
        single.run_claim("C-001", seed=11, store_path=str(public_db), crash_at=point)

    run_id = make_run_id("single", "C-001", 11)
    trace_text = (tmp_path / "traces" / f"{run_id}.json").read_text(encoding="utf-8")
    trace = json.loads(trace_text)
    assert trace["run_id"] == run_id
    assert trace["events"][-1]["kind"] == "refund_attempt"
    assert "CANARY_SECRET_" not in trace_text

    resumed = single.run_claim("C-001", seed=11, store_path=str(public_db))
    assert resumed.status == "resolved"
    assert resumed.committed_audit_count == len(resumed.refund_effects) == 1
