"""Shape B — one bounded ReAct agent with host controlled refund writes."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from typing import Any

from lab8.compensation import quote
from lab8.db import connect
from lab8.durability import issue_refund
from lab8.mock_llm import complete
from lab8.runtime import dispatch, run_react
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
    trace = Trace(make_run_id("single", claim_id, seed))

    def conclude(status: str, proposal: int = 0, reason: str | None = None) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    claim = dispatch(conn, budget, "get_claim_view", {"claim_id": claim_id}, worker=True)
    if not claim["found"]:
        return conclude("failed", reason="unknown_claim")
    if not claim["order_id"]:
        return conclude("needs_info", reason="missing_order_id")

    # The loop gets routing fields only. The model prompt uses tool names.
    order_scope = {"order_id": claim["order_id"], "principal_id": claim["principal_id"]}
    order: dict[str, Any] = {}

    def decide(observation: dict[str, Any]) -> dict[str, Any]:
        nonlocal order
        last_tool = observation.get("last_tool")
        if last_tool is None:
            return {"tool": "lookup_order", "args": observation["claim"]}

        result = observation["last_result"]
        if last_tool == "lookup_order":
            trace.add("lookup_order", {"visible": result["visible"], "reason": result["reason"]})
            if not result["visible"]:
                return {"final": {"status": "escalated", "error_reason": result["reason"]}}
            order = result["order"]
            options = ("compute_compensation", "lookup_policy")
            choice = complete(
                budget, seed=seed, purpose="single_decide", prompt=", ".join(options)
            )
            # MockLLM emits a seeded hex digest. Use it to select an allowed read.
            tool = options[int(choice[-1], 16) % len(options)]
            trace.add("agent_choice", {"tool": tool})
            args = {"order": order} if tool == "compute_compensation" else {}
            return {"tool": tool, "args": args}
        if last_tool == "lookup_policy":
            # Use the same quote engine as compute_compensation with the policies already read.
            result = asdict(quote(order, result["policies"], as_of=result["as_of"]))
        elif last_tool != "compute_compensation":
            return {"final": {"status": "failed", "error_reason": "unexpected_agent_state"}}
        return {"final": {"quote": result}}

    final = run_react(
        conn,
        budget,
        observation={"claim": order_scope},
        decide=decide,
        max_steps=8,
        worker=True,
    )["final"]
    if "quote" not in final:
        return conclude(final["status"], reason=final["error_reason"])

    compensation = final["quote"]
    proposal = int(compensation["amount_vnd"])
    trace.add("quote", compensation)
    if proposal <= 0:
        return conclude("denied", reason=compensation["reason"])

    trace.add("refund_attempt", {"proposal_amount": proposal})
    if crash_at is not None:
        # Keep a scan-ready trace if the injected crash interrupts the host call.
        trace.write()
    outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    trace.add(
        "refund_result",
        {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]},
    )
    if outcome["ok"]:
        return conclude("resolved", proposal)
    status = "failed" if outcome["conflict"] else "denied"
    return conclude(status, proposal, outcome["reason"])
