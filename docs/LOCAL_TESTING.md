# Local naive negotiator

## Environment

Use Python **3.12**: upstream pyproject.toml requires >=3.12,<3.13, and its Dockerfile uses python:3.12-slim. The machine's default Python 3.14 is not suitable for this kit. uv manages a separate compatible interpreter and virtual environment; no change to the default Python is needed.

From the repository root:

```bash
# macOS, if uv is not installed
brew install uv
uv sync --project vendor/negotiation-arena-kit/starter-kit --python 3.12 --frozen --all-extras
```

The environment lives at vendor/negotiation-arena-kit/starter-kit/.venv and is ignored by Git. --frozen uses the checked-in uv.lock without rewriting it. All extras install Anthropic, MCP and simulator support, alongside httpx, openpyxl and pypdf; development dependencies include pytest and Ruff. The naive buyer needs neither LLM credentials nor the real arena key.

## Run a complete test

```bash
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python scripts/test_naive.py
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras python scripts/test_naive.py --case all
```

The default case is case:S01, the adapter-piece price increase. --case also accepts case:S02 (RFQ) and case:S03 (motor framework renewal). The runner starts an HTTP simulator on an available loopback port, loads bundled facts, registers a disposable simulator team, plays the selected cases, prints terms/cost/score and stops the server. The simulator's 60-second rule remains enabled. It does not load .env, call an LLM, or contact the hosted arena. Explicit local credentials prevent accidentally sending a real key even if one is exported in the shell.

Verified on 10 October 2026 using uv 0.13.0, Python 3.12.15 and the locked dependencies:

| Local case | Accepted price | Total cost | Score | Must-haves |
|---|---:|---:|---:|---|
| S01 | EUR 16.59 | EUR 112,451.50 | 0.520602 | Passed |
| S02 | EUR 16.34 | EUR 614,057.20 | 0.513154 | Passed |
| S03 | EUR 227.57 | EUR 3,864,138.60 | 0.677574 | Passed |

The test servers stopped after completion. Upstream pytest: **31 passed, 1 skipped** (hosted credentials deliberately unset). Ruff checks passed for the upstream kit and our runner. All upstream files, including uv.lock, remain unchanged.

Latest local-only implementation check, 10 October 2026: the project suite passed **49 tests** after current-offer, claim-classification and reply-aware changes. `ruff check --select E4,E7,E9,F nighthunter tests` and Python syntax compilation passed. The naive S01–S03 simulator check was rerun with the same scores shown above, all valid deals and zero LLM calls. The test suite uses only in-process logic and mocked HTTP responses; the naive runner binds `127.0.0.1` and supplies a disposable simulator key explicitly. No root `.env`, hosted arena session, OpenAI call or Tacto API call was used. In this managed sandbox, loopback binding required elevated execution; that elevation was for the local simulator only. These scripted scores do **not** measure the revised LLM buyer's negotiation quality.

Case files live in vendor/negotiation-arena-kit/starter-kit/arena_kit/sim_cases/. Supplier behavior is scripted. Success here verifies plumbing and establishes a baseline, not performance against Tacto's actual bots.

## How the naive buyer works

The runner constructs the supplied class:

```python
agent = NaiveAgent(anchor=0.10, close_gap=0.01)
result = play(RemoteTable(client), "case:S01", agent)
```

It selects the quoting supplier with the lowest estimated cost, opens 10% below its price, then offers the midpoint between its last ask and the supplier's price. It accepts when the price gap is within 1%, the supplier agrees or declares a final offer, or rounds run out. It walks away if no live supplier quotes a price.

This is deliberately weak: it does not research evidence, optimize non-price trades, or consistently guard acceptance against must-haves and the alternative. Use it as a benchmark; the later buyer will need the validation and economics described in PLAN.md.

## Upstream checks

Run from the kit directory so its test paths and Ruff configuration apply:

```bash
cd vendor/negotiation-arena-kit/starter-kit
uv run --frozen --all-extras pytest
uv run --frozen --all-extras ruff check .
```

Leave ARENA_TEST_URL and ARENA_TEST_KEY unset for local-only tests. Tests using real model inference are not needed: the suite uses a scripted stand-in. Lint our runner from the repository root with:

```bash
uv run --project vendor/negotiation-arena-kit/starter-kit --frozen --all-extras ruff check --config vendor/negotiation-arena-kit/starter-kit/pyproject.toml scripts
```

## Optional Docker path

The supplied Dockerfile packages the **simulator**, not our buyer. It pins uv 0.11.11 and installs only simulator dependencies in a Python 3.12 image. Docker is optional; the native setup above is sufficient.

From the repository root, with Docker running:

```bash
docker build -t nighthunter-arena-sim vendor/negotiation-arena-kit/starter-kit
docker run --rm -p 127.0.0.1:8080:8080 nighthunter-arena-sim
```

This runs the built-in cases without mounting the larger public fact package. Register a separate simulator key when connecting a client manually. Do not replace your real team key in .env with that temporary key. Docker image build/run has not been validated as part of the native setup.
