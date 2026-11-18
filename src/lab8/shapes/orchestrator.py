"""Shape C — orchestrator plus read-only investigators. Student work.

1. Build a handoff with `lab8.handoff.make_handoff`. Allowed tools are read-only.
   Never put parent_secret, raw headers, or the full claim row into facts.
2. `lab8.runtime.run_readonly_investigators` runs those tools.
3. The orchestrator quotes from the investigator's order view and calls
   `durability.issue_refund`. Investigators have no write registry.
   Pass the full quote; the host subtracts earlier refunds on the same order.
   `lookup_refund_history` is a read-only tool you may hand to an investigator.
4. Trace the sanitized handoff, not the parent context.

An LLM summary of the parent context is not a sanitizer. Use the allowlist.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.handoff import make_handoff
from lab8.mock_llm import complete
from lab8.runtime import dispatch, run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id("orchestrator", claim_id, seed))

    def conclude(status: str, proposal: int = 0, reason: str | None = None) -> RunResult:
        # The model drafts wording only; code owns status, quote, and writes.
        complete(budget, seed=seed, purpose="draft", prompt=f"status={status}; proposal={proposal}")
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    claim = dispatch(conn, budget, "get_claim_view", {"claim_id": claim_id}, worker=False)
    # Do not log or forward the claim view: its ticket is untrusted text.
    if not claim["found"]:
        return conclude("failed", reason="unknown_claim")
    if not claim.get("order_id"):
        return conclude("needs_info", reason="missing_order_id")

    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="check_applicable_policy",
        # Investigator lấy dữ liệu qua tool để handoff không phải mang nội dung ticket.
        facts={},
        # Tính quote cần kết quả tra đơn và tự đọc policy hiện hành.
        allowed_tools=["lookup_order", "compute_compensation"],
    )
    trace.add("handoff", handoff)
    investigated = run_readonly_investigators(
        conn, budget, handoff, principal_id=claim["principal_id"]
    )
    tools = investigated["tools"]
    order_view = tools["lookup_order"]
    trace.add("investigator", {"lookup_order": order_view})
    if not order_view["visible"]:
        return conclude("escalated", reason=order_view["reason"])

    quote = tools["compute_compensation"]
    proposal = int(quote["amount_vnd"])
    trace.add("quote", quote)
    if proposal <= 0:
        return conclude("denied", reason=quote["reason"])

    # Only the orchestrator writes. The host caps the full quote, checks
    # approval, and deduplicates retries. InjectedCrash must propagate.
    if crash_at is not None:
        # Grader cần trace để quét ngay cả khi crash xảy ra trước finish().
        trace.write()
    outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    trace.add("refund", outcome)
    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        return conclude(status, proposal, outcome["reason"])
    return conclude("resolved", proposal)
