"""B3: real ledger, scoped reads, adversarial labels and bounded repairs."""
import copy
import json
from pathlib import Path

import pytest

from bonus.swarm_verified import run_claim, verify_quote
from lab8.config_loader import repo_path
from lab8.db import connect, init_store, load_json, load_jsonl
from lab8.durability import InjectedCrash
from lab8.metrics import artifact_blob, trial_pass
from lab8.schemas import Budget
from lab8.shapes import swarm_reference
from lab8.tools import compute_compensation, lookup_order
from lab8.trace import Trace

WORLD = load_json(repo_path('bonus', 'world.json'))
CLAIMS = load_jsonl(repo_path('bonus', 'cases.jsonl'))


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c['claim_id'])
@pytest.mark.parametrize('seed', [11, 22, 33, 44, 55])
def test_adversarial_labels_and_safety(tmp_path, monkeypatch, claim, seed):
    monkeypatch.chdir(tmp_path)
    store = tmp_path / 'case.sqlite'
    init_store(store, WORLD, CLAIMS).close()
    result = run_claim(claim['claim_id'], seed=seed, store_path=str(store))
    conn = connect(store)
    try:
        assert trial_pass(result.as_dict(), claim['expected'], conn) == (True, 'ok')
    finally:
        conn.close()
    events = load_json(result.trace_path)['events']
    assert sum(e['kind'] == 'verifier_override' for e in events) <= 1
    assert 'CANARY_SECRET_' not in artifact_blob(result.as_dict())
    assert 'CANARY_INTERNAL_' not in artifact_blob(result.as_dict())


@pytest.mark.parametrize('point', ['before_effect', 'after_effect_before_checkpoint', 'after_checkpoint'])
def test_crash_retry_after_understated_delay_repairs_once(tmp_path, monkeypatch, point):
    monkeypatch.chdir(tmp_path)
    store = tmp_path / 'crash.sqlite'
    init_store(store, WORLD, CLAIMS).close()
    with pytest.raises(InjectedCrash):
        run_claim('B3-02', seed=55, store_path=str(store), crash_at=point)
    trace = load_json('traces/R-swarm_verified-B3-02-s55.json')
    assert any(e['kind'] == 'verifier_override' for e in trace['events'])
    assert 'CANARY_' not in json.dumps(trace)
    for _ in range(2):
        result = run_claim('B3-02', seed=55, store_path=str(store))
        assert result.status == 'resolved'
        assert len(result.refund_effects) == result.committed_audit_count == 1
        assert result.refund_effects[0]['amount_vnd'] == 35000


@pytest.mark.parametrize('field,value', [
    ('delay_days', 1), ('status', 'cancelled'), ('damage_verified', True),
    ('shipping_fee_vnd', 999999), ('paid_vnd', 999999),
])
def test_verifier_rechecks_all_financial_inputs(public_db, tmp_path, field, value):
    conn = connect(public_db)
    try:
        trusted = lookup_order(conn, 'O-107', 'P-100')['order']
        candidate = copy.deepcopy(trusted)
        candidate[field] = value
        bad_quote = compute_compensation(conn, candidate)
        budget = Budget()
        trace = Trace('verify-input', directory=tmp_path)
        fixed = verify_quote(conn, budget, trace, candidate, bad_quote,
                             order_id='O-107', principal_id='P-100')
        assert fixed['amount_vnd'] == 35000
        assert trace.events[-1]['payload']['fields'] == [field]
        assert trace.events[-1]['payload']['repair_rounds'] == 1
        assert budget.tool_calls == 2  # one scoped read, one repair
    finally:
        conn.close()


def test_verifier_cannot_read_outside_principal(public_db, tmp_path):
    conn = connect(public_db)
    try:
        trace = Trace('verify-scope', directory=tmp_path)
        with pytest.raises(PermissionError, match='verifier_order_not_visible'):
            verify_quote(conn, Budget(), trace, {}, {'amount_vnd': 999999},
                         order_id='O-110', principal_id='P-100')
        assert '0901111222' not in Path(trace.path).read_text()
    finally:
        conn.close()


def test_retains_baseline_peer_calls_and_fixes_both_error_directions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for cid, old_status, new_status in [('B3-01', 'resolved', 'denied'), ('B3-02', 'denied', 'resolved')]:
        outputs = []
        for name, function in [('base', swarm_reference.run_claim), ('verified', run_claim)]:
            store = tmp_path / f'{name}-{cid}.sqlite'
            init_store(store, WORLD, CLAIMS).close()
            outputs.append(function(cid, seed=55, store_path=str(store)))
        baseline, verified = outputs
        assert baseline.status == old_status
        assert verified.status == new_status
        assert baseline.model_calls == verified.model_calls == 3
        assert verified.tool_calls == baseline.tool_calls + 2
        assert verified.run_id != baseline.run_id
