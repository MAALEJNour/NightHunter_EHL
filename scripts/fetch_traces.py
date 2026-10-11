"""Save the arena's post-session state (with the supplier's reasons) for finished runs. Read-only.

    python scripts/fetch_traces.py artifacts/final_runs/<ts>     # practice/sandbox sessions only
"""

import glob
import json
import os
import sys

from arena_kit import ArenaClient
from arena_kit.cli import load_env

from nighthunter.context import ROOT


def main():
    load_env(ROOT / ".env")
    client = ArenaClient()
    for folder in sys.argv[1:]:
        for session_file in glob.glob(os.path.join(folder, "**/session.json"), recursive=True):
            case_dir = os.path.dirname(session_file)
            target = os.path.join(case_dir, "state.json")
            if os.path.exists(target):
                continue
            sid = json.load(open(session_file))["session_id"]
            state = client.session(sid)
            if state.get("status") == "ended":
                json.dump(state, open(target, "w"), indent=1)
                print("saved", target)
    client.http.close()


if __name__ == "__main__":
    main()
