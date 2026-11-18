"""Measure the effect of disabling the reference swarm's ticket-delay override."""

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from lab8.benchmark import run_benchmark
from lab8.db import load_json, load_jsonl
from lab8.shapes import swarm_reference


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    world = load_json("data/public_world_state.json")
    claims = load_jsonl("data/public_claims.jsonl")
    seeds = [11, 22, 33, 44, 55]
    baseline = run_benchmark(world=world, claims=claims, shapes=["swarm"], seeds=seeds)
    # Swarm uses this result only to gate the override. MockLLM still parses the ticket.
    with patch.object(swarm_reference, "parse_delay_days", return_value=None):
        verified = run_benchmark(world=world, claims=claims, shapes=["swarm"], seeds=seeds)

    report = {
        "variable": "allow the ticket delay to override the verified order delay",
        "controlled_variables": baseline["controlled_variables"],
        "baseline": {
            "summary": baseline["by_shape"]["swarm"],
            "trials": baseline["trials"],
        },
        "verified_order_only": {
            "summary": verified["by_shape"]["swarm"],
            "trials": verified["trials"],
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
