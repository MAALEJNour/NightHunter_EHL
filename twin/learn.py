"""Learn supplier reactions from all saved traces, with case-grouped train / validation / test splits.

    python -m twin.learn               # needs numpy + scikit-learn (scratch env, not the kit's venv)

Splits are by CASE so every score is measured on suppliers the model never saw (as in the final):
fixed split train P01 P02 P03 P04 P07 / validation P10 P11 / test P08 P18, plus leave-one-case-out.
Targets: the supplier's price move as a share of its opening price, and its status. A model earns use
as a policy simulator only if it beats naive baselines on held-out cases. Offline evaluation only.
"""

import json
import statistics
from collections import Counter, defaultdict

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.inspection import permutation_importance

from nighthunter.context import ROOT

TRAIN, VALID, TEST = ("P01", "P02", "P03", "P04", "P07"), ("P10", "P11"), ("P08", "P18")
GOALS = ("stabilise", "leverage", "routine", "secure_supply", "quality_first")
FEATURES = ["round", "gap_before", "sup_from_open", "our_move", "prev_sup_move", "first_depth", "n_sheets",
            "n_claims", "n_verified", "n_contradicted", "new_claims", "volume_answer", "questions",
            "c_notice_period", "c_rival_quote", "c_should_cost", "c_delivery_record", "c_quality_record",
            "c_index_change", "c_price_history", "c_volume_change"] + [f"goal_{g}" for g in GOALS]


def load():
    data = json.loads((ROOT / "artifacts/twin_dataset.json").read_text())
    for r in data:
        r["case_short"] = (r["case"] or "")[-3:]
        for g in GOALS:
            r[f"goal_{g}"] = int(r["goal"] == g)
        r["status3"] = {"open": 0, "final_offer": 1, "agreed": 2}.get(r["y_status"], 0)
    return data


def matrix(rows):
    return np.array([[float(r[f]) for f in FEATURES] for r in rows]), np.array([r["y_move"] for r in rows]), \
        np.array([r["status3"] for r in rows])


def baseline(train, test):
    """Median move by first/later round (and by goal when it has data), learned on the train rows."""
    by = defaultdict(list)
    for r in train:
        by[(r["goal"], r["round"] == 1)].append(r["y_move"])
        by[(None, r["round"] == 1)].append(r["y_move"])
    return np.array([statistics.median(by.get((r["goal"], r["round"] == 1)) or by[(None, r["round"] == 1)])
                     for r in test])


def status_baseline(train, test):
    by = defaultdict(Counter)
    for r in train:
        by[min(r["round"], 5)][r["status3"]] += 1
    return np.array([by[min(r["round"], 5)].most_common(1)[0][0] if by[min(r["round"], 5)] else 0 for r in test])


def fit(train, depth=2, n=300, lr=0.03):
    x, y, s = matrix(train)
    reg = GradientBoostingRegressor(max_depth=depth, n_estimators=n, learning_rate=lr, subsample=0.8,
                                    random_state=0, loss="huber").fit(x, y)
    cls = GradientBoostingClassifier(max_depth=depth, n_estimators=n, learning_rate=lr, subsample=0.8,
                                     random_state=0).fit(x, s)
    return reg, cls


def evaluate(train, test, **params):
    reg, cls = fit(train, **params)
    x, y, s = matrix(test)
    mae_model = float(np.mean(np.abs(reg.predict(x) - y))) * 100
    mae_base = float(np.mean(np.abs(baseline(train, test) - y))) * 100
    acc_model = float(np.mean(cls.predict(x) == s)) * 100
    acc_base = float(np.mean(status_baseline(train, test) == s)) * 100
    return {"mae_model": mae_model, "mae_base": mae_base, "acc_model": acc_model, "acc_base": acc_base,
            "n": len(test)}, reg, cls


def main():
    data = load()
    cases = sorted({r["case_short"] for r in data})
    pick = lambda names: [r for r in data if r["case_short"] in names]  # noqa: E731

    print("== hyper-parameters chosen on the VALIDATION cases (P10, P11) ==")
    best = None
    for depth in (1, 2, 3):
        for n in (100, 300, 600):
            for lr in (0.02, 0.05):
                res, _, _ = evaluate(pick(TRAIN), pick(VALID), depth=depth, n=n, lr=lr)
                score = res["mae_model"] - res["mae_base"]
                if best is None or score < best[0]:
                    best = (score, {"depth": depth, "n": n, "lr": lr}, res)
    params = best[1]
    print(f"best {params}: validation MAE model {best[2]['mae_model']:.3f} vs baseline {best[2]['mae_base']:.3f} "
          f"(% of opening price); status acc {best[2]['acc_model']:.0f}% vs {best[2]['acc_base']:.0f}%")

    res, reg, cls = evaluate(pick(TRAIN + VALID), pick(TEST), **params)
    print(f"\n== TEST cases (P08, P18), trained on train+validation ==\n"
          f"MAE model {res['mae_model']:.3f} vs baseline {res['mae_base']:.3f}; "
          f"status acc {res['acc_model']:.0f}% vs {res['acc_base']:.0f}% (n={res['n']})")

    print("\n== leave-one-case-out (every case held out once) ==")
    wins, rows = 0, []
    for c in cases:
        res, _, _ = evaluate([r for r in data if r["case_short"] != c], pick((c,)), **params)
        wins += res["mae_model"] < res["mae_base"]
        rows.append((c, res))
        print(f"  {c}: MAE model {res['mae_model']:.3f} vs base {res['mae_base']:.3f} | status "
              f"{res['acc_model']:.0f}% vs {res['acc_base']:.0f}% (n={res['n']})")
    mm = statistics.mean(r["mae_model"] for _, r in rows)
    mb = statistics.mean(r["mae_base"] for _, r in rows)
    print(f"  mean: model {mm:.3f} vs baseline {mb:.3f}; model better on {wins}/{len(cases)} held-out cases")

    print("\n== what drives the supplier's move (permutation importance on held-out TEST cases) ==")
    x, y, _ = matrix(pick(TEST))
    imp = permutation_importance(reg, x, y, n_repeats=20, random_state=0, scoring="neg_mean_absolute_error")
    for i in np.argsort(-imp.importances_mean)[:10]:
        print(f"  {FEATURES[i]:20} {imp.importances_mean[i] * 100:+.4f}")

    print("\n== effect of OUR choices, all data (model trained on everything; directions, not proof) ==")
    reg_all, cls_all = fit(data, **params)
    later = [r for r in data if r["round"] >= 2]
    x_later = matrix(later)[0]
    for feature, values in (("our_move", (0.0, 0.01, 0.02, 0.04)), ("new_claims", (0, 1, 2)),
                            ("volume_answer", (0, 1)), ("questions", (0, 1, 2)), ("n_sheets", (1, 2, 3))):
        j = FEATURES.index(feature)
        out = []
        for v in values:
            xx = x_later.copy()
            xx[:, j] = v
            move = float(np.mean(reg_all.predict(xx))) * 100
            final = float(np.mean(cls_all.predict_proba(xx)[:, 1])) * 100
            out.append(f"{v}: move {move:.2f}% final {final:.0f}%")
        print(f"  later rounds, {feature:13} " + " | ".join(out))
    first = [r for r in data if r["round"] == 1]
    x_first = matrix(first)[0]
    j = FEATURES.index("first_depth")
    k = FEATURES.index("gap_before")
    out = []
    for depth in (0.03, 0.06, 0.10, 0.15, 0.22, 0.30):
        xx = x_first.copy()
        xx[:, j] = depth
        xx[:, k] = xx[:, k] * 0 + depth  # first ask's gap equals its depth in round 1
        out.append(f"{depth:.2f}: {float(np.mean(reg_all.predict(xx))) * 100:.2f}%")
    print("  round 1, first-ask depth -> first reply move: " + " | ".join(out))
    (ROOT / "artifacts/twin_learn_params.json").write_text(json.dumps(params))


if __name__ == "__main__":
    main()
