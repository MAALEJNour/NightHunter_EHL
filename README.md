# NightHunter_EHL

Our entry for the **Tacto Negotiation Arena**: an autonomous procurement agent for the fictional pump manufacturer Hollerau Pumpenwerke.

The objective is to negotiate the best **total-cost deal** that satisfies the case's must-haves, or choose the available alternative. Unit price is only one component of the score.

## Project status

Planning and source inspection completed on 10 October 2026. The complete upstream snapshot (323 files) and a private `.env` template are now available locally. No custom negotiator has been implemented, dependencies installed, or hosted negotiation sessions opened here.

- [Discovery and implementation plan](docs/PLAN.md): rules, data, architecture, tools, milestones, validation and open questions.
- [Presentation notes](docs/PRESENTATION_NOTES.md): your notes, with differences from the written rules recorded explicitly.
- [Agent instructions](AGENTS.md): how future coding agents should work on this project and maintain its documentation.

## Source material

Upstream: [tacto-ai/negotiation-arena-kit](https://github.com/tacto-ai/negotiation-arena-kit), inspected at commit `1b5516bb95ef28e37f69aa446dc62168864bca53`.

The source was first inspected separately, then imported at your request into [vendor/negotiation-arena-kit](vendor/negotiation-arena-kit/README.md). All tracked upstream files are included, without its Git history. See [provenance and licenses](docs/UPSTREAM.md).

Start with upstream's [brief](https://github.com/tacto-ai/negotiation-arena-kit/blob/1b5516bb95ef28e37f69aa446dc62168864bca53/brief/brief.md), [API contract](https://github.com/tacto-ai/negotiation-arena-kit/blob/1b5516bb95ef28e37f69aa446dc62168864bca53/brief/api.md), [starter kit](https://github.com/tacto-ai/negotiation-arena-kit/blob/1b5516bb95ef28e37f69aa446dc62168864bca53/starter-kit/README.md), and [submission requirements](https://github.com/tacto-ai/negotiation-arena-kit/blob/1b5516bb95ef28e37f69aa446dc62168864bca53/brief/submission.md).

## Proposed pipeline

Read case and supplier history → build a dossier with source IDs → calculate candidate packages → negotiate and update the dossier → validate and accept the best standing offer, or walk away → evaluate the replay.

Use an LLM for interpretation and business communication; use deterministic code for money, evidence checks, legal API values, deadlines and closing decisions. Logical specialist roles can share one orchestrator; multiple model calls are an experiment, not a prerequisite.

## Setup prerequisites

The supplied kit requires **Python 3.12** and `uv`. We also need one team arena key and our own LLM access. Keep credentials in an untracked environment file or environment variables; never paste them into documentation or commits.

Open the root `.env` and fill in `ARENA_API_KEY=your_team_key`. The file is ignored by Git; [.env.example](.env.example) is the shareable template with blank credentials. LLM settings can remain blank until we choose a model.

After Python 3.12 and `uv` are installed, run these from **this repository's root**:

```bash
uv sync --project vendor/negotiation-arena-kit/starter-kit --all-extras
uv run --project vendor/negotiation-arena-kit/starter-kit arena me
uv run --project vendor/negotiation-arena-kit/starter-kit arena cases --set practice
```

Keep the working directory here: the kit reads `.env` from the current directory, and `ARENA_DATA` points to the bundled data. These commands are documented but have not been run. `arena me` verifies the team account; listing cases does not start a negotiation. The custom agent's implementation and run command remain pending.

## Feasibility

Building a functioning autonomous buyer is feasible with this kit. Competitive performance needs measured experiments; a winning score cannot be promised. The repository supplies the public data and simulator, but the real supplier bots and hidden final cases remain hosted by Tacto. LLM access, a compatible environment and final-machine testing are still required.

## Development workflow with Entire

1. Work with the coding agent to make and review a change.
2. Commit the change with a descriptive message.
3. Push the commit and check the terminal output for Entire's checkpoint upload confirmation.

With Entire enabled and its agent hooks approved, session checkpoints can accompany your normal Git workflow.
