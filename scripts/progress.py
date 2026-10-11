"""Live progress of the latest run (final-runner rehearsal/final, or a strategy batch). Read-only.

    python3 scripts/progress.py            # latest artifacts/final_runs/* folder
    python3 scripts/progress.py --batch    # latest artifacts/strategies/* batch
"""

import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    pattern = "artifacts/strategies/*/" if "--batch" in sys.argv else "artifacts/final_runs/2*/"
    folders = sorted((f for f in glob.glob(os.path.join(ROOT, pattern))
                      if "--batch" in sys.argv or glob.glob(f + "case_P*") or glob.glob(f + "case_[0-9A-Z]*[0-9]")),
                     key=os.path.getmtime)
    folders = [f for f in folders if "--batch" in sys.argv or not glob.glob(f + "case_S0*")]
    if not folders:
        print("no runs yet")
        return
    run = folders[-1]
    print(run)
    cases = sorted(glob.glob(run + "case_*") + glob.glob(run + "P*/*/"))
    for case in cases:
        if not os.path.isdir(case):
            continue
        try:
            conv = json.load(open(os.path.join(case, "conversation.json")))
        except (OSError, ValueError):
            print(f"  {os.path.relpath(case, run):18} starting")
            continue
        sent = sum(e["who"] == "Buyer (submitted)" for e in conv)
        stamps = [e["at"] for e in conv if isinstance(e.get("at"), (int, float)) and 1e9 < e["at"] < 1e10]
        age = f"{time.time() - stamps[-1]:.0f}s ago" if stamps else ""
        result = None
        for name in ("result.json", "summary.json"):
            path = os.path.join(case, name)
            if os.path.exists(path):
                data = json.load(open(path))
                result = data.get("result", data) if isinstance(data.get("result", data), dict) else data
                break
        if result and (result.get("score") is not None or result.get("error")):
            score = result.get("score")
            status = f"DONE  score {score * 100:.1f}" if isinstance(score, (int, float)) else f"ended {result.get('error') or ''}"
            if result.get("elapsed_s"):
                status += f"  in {result['elapsed_s']:.0f}s"
        else:
            status = f"negotiating, last: {conv[-1]['who']} {age}"
        print(f"  {os.path.relpath(case, run):18} {sent} e-mails sent   {status}")


if __name__ == "__main__":
    main()
