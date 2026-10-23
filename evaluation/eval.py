"""Measures precision and recall of the rules engine on a labelled set of snippets.

Run:  python3 evaluation/eval.py
The cases were written by the developers, so scores describe this set, not real-world performance.
"""
import collections
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from app import engine  # noqa: E402

kit = json.load(open(os.path.join(ROOT, "data", "brandkit.json")))
CASES_FILE = sys.argv[1] if len(sys.argv) > 1 else "cases.json"
cases = json.load(open(os.path.join(ROOT, "evaluation", CASES_FILE)))
today = datetime.date(2026, 10, 21)
tp, fp, fn = collections.Counter(), collections.Counter(), collections.Counter()
misses = []
for c in cases:
    got = {f["rule_id"] for f in engine.review(kit, c["kind"], c["text"], today)["findings"]}
    exp = set(c["expect"])
    for r in got & exp:
        tp[r] += 1
    for r in got - exp:
        fp[r] += 1
        misses.append(f"{c['id']}: unexpected {r}")
    for r in exp - got:
        fn[r] += 1
        misses.append(f"{c['id']}: missed {r}")
rules = sorted(set(tp) | set(fp) | set(fn))
print(f"{'rule':20} {'TP':>3} {'FP':>3} {'FN':>3} {'precision':>9} {'recall':>7}")
for r in rules:
    p = tp[r] / (tp[r] + fp[r]) if tp[r] + fp[r] else 1.0
    rc = tp[r] / (tp[r] + fn[r]) if tp[r] + fn[r] else 1.0
    print(f"{r:20} {tp[r]:>3} {fp[r]:>3} {fn[r]:>3} {p:>9.2f} {rc:>7.2f}")
T, F, N = sum(tp.values()), sum(fp.values()), sum(fn.values())
print(f"\nOVERALL cases={len(cases)} TP={T} FP={F} FN={N} precision={T/(T+F):.3f} recall={T/(T+N):.3f}")
if misses:
    print("\nDisagreements:")
    print("\n".join(misses))
