"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item

def utf8_stdio() -> None:
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    import math
    problems: list[str] = []
    def finite(value, path):
        if isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isfinite(value):
            problems.append(f"non-finite value at {path}")
        elif isinstance(value, dict):
            for k, v in value.items(): finite(v, f"{path}.{k}")
        elif isinstance(value, list):
            for i, v in enumerate(value): finite(v, f"{path}[{i}]")
    finite(pr.get("metrics", {}), "metrics")
    expected = pr.get("manifest", {}).get("items", 0) * len(pr.get("manifest", {}).get("seeds", []))
    rows = pr.get("rows", [])
    if len(rows) != expected: problems.append(f"row count {len(rows)} != expected {expected}")
    base_pairs = {(r.get("item_id"), r.get("seed")) for r in base.get("rows", [])}
    pr_pairs = [(r.get("item_id"), r.get("seed")) for r in rows]
    if len(pr_pairs) != len(set(pr_pairs)): problems.append("duplicate (item_id, seed) rows")
    if set(pr_pairs) != base_pairs: problems.append("(item_id, seed) set differs from baseline")
    if pr.get("evaluator_failures"): problems.append("evaluator_failures is non-empty")
    graded = {m["id"] for m in spec.get("metrics", []) if m.get("grader") in ("code", "lab8.metrics.trial_pass")}
    for i, row in enumerate(rows):
        for metric in graded:
            if metric in row and row[metric] is None:
                problems.append(f"row {i} has null graded metric {metric}")
        if i < len(base.get("rows", [])) and row.get("slices", []) != base["rows"][i].get("slices", []):
            problems.append(f"row {i} slice tags differ from baseline")
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        old = {m["id"]: m for m in base_spec.get("metrics", [])}
        new = {m["id"]: m for m in spec.get("metrics", [])}
        for mid, om in old.items():
            if mid not in new:
                problems.append(f"ratchet removed metric {mid}"); continue
            nm = new[mid]; ot, nt = om.get("threshold", {}), nm.get("threshold", {})
            if om.get("blocking") and not nm.get("blocking"): problems.append(f"ratchet made {mid} non-blocking")
            if "min" in ot and ("min" not in nt or nt["min"] < ot["min"]): problems.append(f"ratchet loosened min for {mid}")
            if "max" in ot and ("max" not in nt or nt["max"] > ot["max"]): problems.append(f"ratchet loosened max for {mid}")
            if ot.get("no_significant_drop") and not nt.get("no_significant_drop"): problems.append(f"ratchet removed no_significant_drop for {mid}")
        old_slices = {s["name"]: s for s in base_spec.get("slices", [])}
        new_slices = {s["name"]: s for s in spec.get("slices", [])}
        for name, os in old_slices.items():
            if name not in new_slices: problems.append(f"ratchet removed slice {name}"); continue
            ns = new_slices[name]
            if os.get("blocking") and not ns.get("blocking"): problems.append(f"ratchet made slice {name} non-blocking")
            if "min" in os and ("min" not in ns or ns["min"] < os["min"]): problems.append(f"ratchet loosened slice {name}")
            if os.get("no_significant_drop") and not ns.get("no_significant_drop"): problems.append(f"ratchet removed slice no_significant_drop {name}")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for entry in spec.get("slices", []):
        name, metric = entry["name"], entry["metric"]
        cur, old = per_item(pr, metric, name), per_item(base, metric, name)
        value = sum(cur.values()) / len(cur) if cur else None
        verdict = "ok"
        note = ""
        if value is None:
            verdict = "missing"
        elif "min" in entry and value < entry["min"]:
            verdict = "fail"
        if entry.get("no_significant_drop") and cur and old:
            keys = sorted(set(cur) & set(old))
            if keys:
                d, lo, hi = stats.paired_bootstrap([cur[k] for k in keys], [old[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0: verdict = "fail"
        label = "BLOCK" if verdict == "fail" else verdict
        lines.append(f"  slice:{name}/{metric} {value!s} {note} {label}")
        if verdict != "ok" and entry.get("blocking"):
            blocked.append(f"slice:{name}/{metric}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
