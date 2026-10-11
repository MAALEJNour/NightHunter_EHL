"""Overnight offline learning: rebuild the dataset, re-learn, and bootstrap every within-case rule.

    python -m twin.overnight [--boot 300]      # scratch env with numpy + scikit-learn

1. Rebuild artifacts/twin_dataset.json from every saved trace (ours + teammate, deduplicated).
2. Supplier-response model with case-grouped splits (twin.learn): does it beat naive baselines?
3. Within-case rules (twin.within_case) re-estimated on bootstrap resamples of the runs: a rule counts
   as robust only if its sign holds on train AND validation AND test cases in >= 80 % of resamples.
4. Deal endings: score when the supplier "agreed" to our package vs when we took its final offer.
Writes artifacts/overnight_report.json. Offline evaluation only - nothing here is a live input.
"""

import argparse
import json
import random
import statistics
from collections import defaultdict

import numpy as np

from nighthunter.context import ROOT
from twin import dataset, within_case
from twin.learn import TEST, TRAIN, VALID

RULES = ["first_depth", "step2_share", "n_msgs", "n_claims_r1", "later_claims", "scorecard_r1", "index_r1",
         "should_cost_r1"]


def ranks(a):
    return np.argsort(np.argsort(a)).astype(float)


def partial(rows, x, ctrl="first_reply_move"):
    pts = [(r[x], r[ctrl], r["score"]) for r in rows if r.get(x) is not None and r.get(ctrl) is not None]
    if len(pts) < 6:
        return None
    xs, cs, ys = (ranks(np.array([p[i] for p in pts], float)) for i in range(3))

    def resid(a, b):
        b1 = np.c_[np.ones(len(b)), b]
        return a - b1 @ np.linalg.lstsq(b1, a, rcond=None)[0]

    rx, ry = resid(xs, cs), resid(ys, cs)
    return None if rx.std() == 0 or ry.std() == 0 else float(np.corrcoef(rx, ry)[0, 1])


def group_mean(corr, group):
    vals = [corr[c] for c in group if corr.get(c) is not None]
    return statistics.mean(vals) if vals else None


def bootstrap(runs, n, seed=7):
    rng = random.Random(seed)
    out = {}
    for rule in RULES:
        signs = []
        for _ in range(n):
            sample = {c: [rng.choice(v) for _ in v] for c, v in runs.items()}
            corr = {c: partial(sample[c], rule) for c in sample}
            g = [group_mean(corr, grp) for grp in (TRAIN, VALID, TEST)]
            if None in g:
                continue
            signs.append(1 if all(v > 0 for v in g) else -1 if all(v < 0 for v in g) else 0)
        if signs:
            out[rule] = {"all_positive": signs.count(1) / len(signs), "all_negative": signs.count(-1) / len(signs),
                         "samples": len(signs)}
    return out


def endings(runs):
    res = {}
    for c, rows in runs.items():
        by = defaultdict(list)
        for r in rows:
            by["agreed" if r["ended_agreed"] else "final" if r["ended_final"] else "other"].append(r["score"])
        res[c] = {k: (len(v), round(statistics.mean(v), 1)) for k, v in by.items()}
    return res


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot", type=int, default=300)
    args = parser.parse_args()
    data = dataset.rows()
    (ROOT / "artifacts/twin_dataset.json").write_text(json.dumps(data, indent=1))
    runs = within_case.collect()
    ours = {c: [r for r in v if r["source"] == "ours"] for c, v in runs.items()}
    report = {"replies": len(data), "runs": {c: len(v) for c, v in runs.items()},
              "bootstrap_ours": bootstrap(ours, args.boot), "bootstrap_all": bootstrap(runs, args.boot),
              "endings_ours": endings(ours)}
    (ROOT / "artifacts/overnight_report.json").write_text(json.dumps(report, indent=2))
    print(f"{len(data)} replies, runs per case {report['runs']}")
    for label in ("bootstrap_ours", "bootstrap_all"):
        print(f"\n{label}: share of {args.boot} resamples where the rule's sign holds on train+valid+test")
        for rule, v in report[label].items():
            verdict = "ROBUST +" if v["all_positive"] >= 0.8 else "ROBUST -" if v["all_negative"] >= 0.8 else "not robust"
            print(f"  {rule:16} +:{v['all_positive']:.2f}  -:{v['all_negative']:.2f}  {verdict}")
    print("\nendings (ours):", json.dumps(report["endings_ours"]))


if __name__ == "__main__":
    main()
