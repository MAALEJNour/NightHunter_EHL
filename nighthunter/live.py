"""One hosted practice negotiation with a real LLM, budget ledger and readable replay."""

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from arena_kit import ArenaClient, RemoteTable, play
from arena_kit.agents.llm import ID_RE, LLMAgent, parse
from arena_kit.cli import load_env
from arena_kit.client import ArenaError
from arena_kit.cost import cost_breakdown, must_haves_ok, total_cost
from arena_kit.data import DataPackage
from arena_kit.docs import standard_terms
from arena_kit.play import latest, live_threads, moves_left, standing

from .context import DEFAULT_DATA, ROOT, CaseContextBuilder, encoded
from .economics import advise, supplier_estimate
from .experiment import VARIANTS
from .packages import plan_packages
from .prose import compose
from .session import is_price_only_cut, thread_observations
from .supplier_profile import build_profile, session_signals
from .validation import REQUESTS, available_claim_cards, claim_cards, render_message, validate_sheets


def buyer_offer_history(events):
    """Compact offers from this thread only, with the next observed supplier reply."""
    history = []
    for i, event in enumerate(events):
        if event.get("from") != "buyer" or not event.get("term_sheets"):
            continue
        reply = next((m for m in events[i + 1:] if m.get("from") != "buyer"), None)
        history.append({"buyer_round": len(history) + 1,
                        "packages": [sheet["terms"] for sheet in event["term_sheets"]],
                        "next_supplier_status": reply.get("status") if reply else None})
    return history


def sourced_profile(profile):
    """Expose tactic provenance without changing the supplier-profile module's output."""
    signals = {}
    for signal in profile.get("signals", []):
        if signal.get("ref"):
            signals.setdefault(signal["kind"], set()).add(signal["ref"])
    kinds = {"request_approval": ("approval_threshold",),
             "trade_non_price_terms": ("price_freeze", "open_terms"),
             "price_early_payment": ("cash_request", "credit_worsening"),
             "request_cost_breakdown": ("stale_costing",),
             "acknowledge_partnership": ("relationship_appeal",)}
    tactics = []
    for tactic in profile.get("tactics", []):
        refs = set(tactic.get("refs", []))
        for kind in kinds.get(tactic["tactic"], ()):
            refs.update(signals.get(kind, ()))
        tactics.append({**tactic, "refs": sorted(refs),
                        "provenance": "source_linked" if refs else "heuristic_no_direct_ref"})
    return {**profile, "tactics": tactics}


# USD per million (input, output) tokens, verified on the official model pages on 2026-10-10:
# developers.openai.com/api/docs/models/gpt-5.6-luna and .../gpt-6-sol; gpt-6-astra on
# developers.openai.com/api/docs/pricing. Add a model only after checking.
PRICES = {"gpt-5.6-luna": (0.20, 1.20), "gpt-6-sol": (2.00, 10.00), "gpt-6-astra": (10.00, 50.00)}
RUN_LIMIT_MAX = 2.0   # explicit per-run override ceiling (--run-limit-usd); default run limit stays 0.75
TOTAL_LIMIT_USD = 7  # cumulative practice/live cap; owner raised it from 5 to 7 on 2026-10-10
# Codex task 3 (default OFF, untested live): say "Payment terms are fixed at 60 days net in this
# agreement." when the supplier asks to change a term the case fixes (LiveAgent.fixed_term_answer).
FIXED_TERM_ANSWER = True  # live P11 11 Oct: sentence sent, 79.4 (= best; recent default runs 71.0)


class BudgetedModel:
    """Conservative cumulative accounting; timed-out calls retain their full reservation.

    Prices per model in PRICES (verified 2026-10-10).
    Ignore cached-input discounts and add 25% input margin for cache writes.
    Text-only input: UTF-8 byte count plus framing allowance bounds input token count.
    This ledger covers this runner only, not independent API clients or billing adjustments.
    """

    def __init__(self, ledger, run_limit=0.75, batch_start_index=None, batch_limit_usd=None, model=None,
                 total_limit_usd=TOTAL_LIMIT_USD):
        self.name = model or os.environ.get("LLM_MODEL")
        if self.name not in PRICES:
            raise ValueError("Confirm model and pricing before changing the configured model")
        self.price_in, self.price_out = PRICES[self.name]
        if os.environ.get("LLM_BASE_URL", "").rstrip("/") != "https://api.openai.com/v1":
            raise ValueError("This priced adapter requires the official OpenAI endpoint")
        if not os.environ.get("LLM_API_KEY"):
            raise ValueError("Missing LLM_API_KEY")
        self.path = Path(ledger)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = self.path.with_suffix(".lock").open("a")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.records = json.loads(self.path.read_text()) if self.path.exists() else []
        self.start = len(self.records)
        if (batch_start_index is None) != (batch_limit_usd is None):
            raise ValueError("Batch start index and spending limit must be supplied together")
        if batch_start_index is not None and (not 0 <= batch_start_index <= self.start
                                              or not 0 < batch_limit_usd <= total_limit_usd):
            raise ValueError("Invalid batch budget guard")
        self.batch_start_index, self.batch_limit_usd = batch_start_index, batch_limit_usd
        self.run_limit = min(run_limit, RUN_LIMIT_MAX)
        self.total_limit = total_limit_usd
        self.max_calls = 12  # RFQ runner raises this for several parallel threads (still budget-capped)
        self.reasoning_effort, self.max_output = "low", 2048  # same model and price; effort is a setting
        self.http = httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=False)

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.records, indent=2) + "\n")
        tmp.replace(self.path)

    def complete(self, system, user, max_output=None):
        max_output = max_output or self.max_output
        size = len((system + user).encode("utf-8"))
        if size > 110000:
            raise ValueError("Input exceeded 110k-byte live-context limit")
        reserve = ((size + 512) * self.price_in * 1.25 + max_output * self.price_out) / 1_000_000
        spent = sum(r["accounted_usd"] for r in self.records)
        run_spent = sum(r["accounted_usd"] for r in self.records[self.start:])
        if spent + reserve > self.total_limit or run_spent + reserve > self.run_limit:
            raise ValueError("Budget exhausted before request")
        if (self.batch_start_index is not None and
                sum(r["accounted_usd"] for r in self.records[self.batch_start_index:]) + reserve
                > self.batch_limit_usd + 1e-12):
            raise ValueError("Batch budget exhausted before request")
        if len(self.records) - self.start >= self.max_calls:
            raise ValueError("Per-run call limit reached")
        record = {"model": self.name, "state": "reserved", "accounted_usd": reserve,
                  "input_bytes": size, "max_output_tokens": max_output,
                  "at": datetime.now(UTC).isoformat()}
        self.records.append(record)
        self.save()  # reserve before any network request, including unknown-outcome failures
        started = time.monotonic()
        try:
            response = self.http.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
                json={"model": self.name, "reasoning_effort": self.reasoning_effort,
                      "max_completion_tokens": max_output, "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            )
            if response.status_code >= 400:
                # Record only status/code; error bodies may contain private details.
                record["http_status"] = response.status_code
                try:
                    record["error_code"] = response.json().get("error", {}).get("code")
                except ValueError:
                    pass
                raise RuntimeError(f"Model HTTP {response.status_code}; code={record.get('error_code')}")
            result = response.json()
            usage = result.get("usage")
            if usage and "prompt_tokens" in usage and "completion_tokens" in usage:
                record["usage"] = usage
                record["accounted_usd"] = (
                    usage["prompt_tokens"] * self.price_in * 1.25 + usage["completion_tokens"] * self.price_out
                ) / 1_000_000
            record["state"] = "completed" if usage else "completed_usage_unknown"
            content = result["choices"][0]["message"]["content"]
            if not content:
                raise ValueError("Empty model response")
            return content
        except Exception:
            if record["state"] == "reserved":
                record["state"] = "failed_reservation_retained"
            raise
        finally:
            record["seconds"] = round(time.monotonic() - started, 3)
            self.save()

    def close(self):
        self.http.close()
        self.lock.close()


class LiveAgent(LLMAgent):
    def __init__(self, model, package, dossier, variant, folder, policy="current", input_version="current",
                 adaptation="current"):
        super().__init__(model.complete, package)
        self.model, self.dossier, self.folder = model, dossier, folder
        self.policy, self.input_version, self.adaptation = policy, input_version, adaptation
        self.case_id, self.brief = dossier["case"]["case_id"], encoded(dossier)
        self.system = (ROOT / "prompts/common.md").read_text() + "\n" + (ROOT / f"prompts/{variant}.md").read_text()
        self.system += (
            "\nLIVE RULES: No retrieval tools are available in this run. Use only the supplied dossier and "
            "live messages. Supplier-cost scenarios are estimates, not verified claims. Do not cite "
            "IDs with unsupported numerical assertions. Keep e-mails below 120 words."
        )
        if policy == "economics":
            self.system += "\n" + (ROOT / "prompts/economics_policy.md").read_text()
        elif policy == "packages":
            self.system += "\n" + (ROOT / "prompts/packages_policy.md").read_text()
        if input_version == "offer_history":
            self.system += "\n" + (ROOT / "prompts/offer_history.md").read_text()
        elif input_version == "buyer_history":
            self.system += "\n" + (ROOT / "prompts/buyer_history.md").read_text()
        if adaptation == "reply_aware":
            self.system += "\n" + (ROOT / "prompts/reply_aware.md").read_text()
        elif adaptation == "expert_prose":
            if policy != "packages":
                raise ValueError("expert_prose requires --policy packages")
            # S1: the model obeyed the earlier "only tone, intent and claim_ids" rule and wrote no
            # framing in 31/31 decisions. Remove that restriction and end with the exact format.
            self.system = self.system.replace(
                "Reply with one JSON object containing only `tone`, `intent`,\nand `claim_ids`.",
                "Reply with one JSON object as specified in EXPERT E-MAIL below.")
            self.system += "\n" + (ROOT / "prompts/expert_prose.md").read_text()
        self.decisions = []
        self.disabled = False
        # A non-primary supplier sheet is a negotiable proposal, not an accept-ready ID.
        # Remember a single-sheet echo until the supplier replies with a primary offer.
        self.pending_alternative = {}
        facts = {**package.facts, **dossier["case"].get("facts", {})}
        self.cards = {sid: claim_cards(dossier["case"], dossier, facts, sid)
                      for sid in dossier["case"]["suppliers"]}
        self.used_refs = set()
        self.profiles = ({sid: build_profile(dossier["case"], dossier, sid)
                         for sid in dossier["case"]["suppliers"]} if policy == "packages" else {})

    def costs(self, case, sid, terms, std):
        values = [total_cost(case, terms, std)]
        estimate = supplier_estimate(case, self.dossier, sid, std)
        if estimate and case["buyer"].get("category_goal") in {"stabilise", "secure_supply"}:
            # Central estimate decides; the range is diagnostic, never an actual charge.
            for factor in (0.95, 1, 1.05):
                values.append(total_cost(case, terms, std,
                                         {**estimate, "full_cost": estimate["full_cost"] * factor}))
        return values

    def current_offers(self, case, threads):
        """Only sheets in each live supplier's latest reply can be accepted.

        Missing negotiable fields must have an actual supplier quote default. Never
        replace one with the buyer's plan or reuse a sheet from an older reply.
        """
        offers = []
        for sid in live_threads(threads):
            events = threads[sid]
            std = standard_terms(events)
            for index, sheet in enumerate(latest(events).get("term_sheets") or []):
                offer_id, terms = sheet.get("term_sheet_id"), sheet.get("terms")
                if not isinstance(offer_id, str) or not offer_id.startswith("offer:") or not isinstance(terms, dict):
                    continue
                if any(field not in terms and field not in std for field in case["negotiable"]):
                    continue
                completed = {field: terms.get(field, std.get(field)) for field in case["negotiable"]}
                try:
                    validate_sheets(case, [completed], std)
                    costs = self.costs(case, sid, terms, std)
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
                central = costs[2] if len(costs) == 4 else costs[0]
                if math.isfinite(central):
                    estimate = supplier_estimate(case, self.dossier, sid, std)
                    components = cost_breakdown(case, terms, std, estimate)
                    offers.append({"supplier_id": sid, "term_sheet_id": offer_id,
                                   "is_primary": index == 0,
                                   "terms": completed, "estimated_total_cost": central,
                                   "cost_scenarios": costs,
                                   "cost_components": {key: round(value, 2)
                                                       for key, value in components.items() if value}})
        return sorted(offers, key=lambda offer: (offer["estimated_total_cost"],
                                                  offer["supplier_id"], offer["term_sheet_id"]))

    def safe_close(self, case, threads, *, allow_counter=True):
        """Accept only a validated primary ID; echo a better alternative once if time permits."""
        if not hasattr(self, "pending_alternative"):
            self.pending_alternative = {}
        alt = case["buyer"].get("alternative") or {}
        alternative = total_cost(case, alt["terms"]) if alt.get("terms", {}).get("unit_price") else math.inf
        offers = [offer for offer in self.current_offers(case, threads)
                  if offer["estimated_total_cost"] < alternative]
        primaries = [offer for offer in offers if offer["is_primary"]]
        for sid, pending in list(self.pending_alternative.items()):
            if sid not in threads or sid not in live_threads(threads):
                self.pending_alternative.pop(sid, None)
                continue
            if len(threads[sid]) > pending["event_count"]:
                self.pending_alternative.pop(sid, None)
                replied = next((offer for offer in primaries if offer["supplier_id"] == sid), None)
                if replied:
                    return {"supplier_id": sid, "message": {"action": {
                        "type": "accept", "term_sheet_id": replied["term_sheet_id"]}}}
        best = offers[0] if offers else None
        if best and best["is_primary"]:
            return {"supplier_id": best["supplier_id"],
                    "message": {"action": {"type": "accept", "term_sheet_id": best["term_sheet_id"]}}}
        if best and allow_counter and moves_left(case, threads[best["supplier_id"]]) > 0:
            sid = best["supplier_id"]
            std = standard_terms(threads[sid])
            render_case = case if case.get("title") else {**case, "title": case["case_id"]}
            message, _ = render_message({"tone": "polite", "intent": "counteroffer",
                                         "claim_ids": [], "term_sheets": [best["terms"]]},
                                        {}, getattr(self, "used_refs", set()), render_case, std)
            self.pending_alternative[sid] = {"event_count": len(threads[sid]),
                                             "terms": best["terms"]}
            return {"supplier_id": sid, "message": message}
        if primaries:
            primary = primaries[0]
            return {"supplier_id": primary["supplier_id"],
                    "message": {"action": {"type": "accept", "term_sheet_id": primary["term_sheet_id"]}}}
        return {"supplier_id": live_threads(threads)[0], "message": {"action": {"type": "walk_away"}}}

    def record_decision(self, record, decision):
        record["executed"] = decision
        self.decisions.append(record)
        (self.folder / "decisions.json").write_text(json.dumps(self.decisions, indent=2) + "\n")
        print(f"Decision {len(self.decisions)}: {'fallback' if record['fallback'] else 'LLM'}", flush=True)
        return decision

    def nonprice_counter(self, case, sid, threads, observations):
        """Replace a frozen-price repeat with a costed, allowed non-price request."""
        events = threads[sid]
        if moves_left(case, events) <= 1 or latest(events).get("status") in {"agreed", "final_offer"}:
            return None
        available = [offer for offer in self.current_offers(case, {sid: events})]
        if not available:
            return None
        base = available[0]
        std = standard_terms(events)
        advice = advise(case, self.dossier, sid, base["terms"], std, events)
        flexible = set(observations.get("flexible_fields_reported") or [])
        choices = []
        for row in advice.get("candidates", []):
            candidate = {**row["terms"], "unit_price": base["terms"]["unit_price"]}
            changed = {field for field in case["negotiable"] if field != "unit_price"
                       and candidate.get(field) != base["terms"].get(field)}
            if not changed or (flexible and not changed <= flexible):
                continue
            try:
                validate_sheets(case, [candidate], std)
                costs = self.costs(case, sid, candidate, std)
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            central = costs[2] if len(costs) == 4 else costs[0]
            if central < base["estimated_total_cost"]:
                choices.append((central, candidate))
        choices.sort(key=lambda item: item[0])
        selected = []
        for _, candidate in choices:
            if candidate not in selected:
                selected.append(candidate)
            if len(selected) == 2:
                break
        if not selected:
            return None
        message, _ = render_message({"tone": "partnership", "intent": "clarify",
                                     "claim_ids": [], "term_sheets": selected}, {},
                                    self.used_refs, case, std)
        return self.guard(case, threads, {"supplier_id": sid, "action": "send", **message})

    def decide(self, case, threads):
        if self.policy == "packages":
            return self.decide_packages(case, threads)
        record = {"decision": len(self.decisions) + 1, "fallback": False}
        if any(sid in threads and len(threads[sid]) > pending["event_count"]
               for sid, pending in self.pending_alternative.items()):
            decision = self.safe_close(case, threads)
            record["close_reason"] = "alternative_echo_reply"
            return self.record_decision(record, decision)
        try:
            if self.disabled:
                raise ValueError("Model disabled after previous error")
            state = {}
            observations = {}
            for sid in live_threads(threads):
                offer, terms = standing(threads[sid])
                std = standard_terms(threads[sid])
                available_cards = available_claim_cards(
                    self.cards[sid], self.used_refs,
                    filter_used=self.input_version in {"unused_claims", "offer_history"})
                state[sid] = {"offer_id": offer, "terms": terms, "standard_terms": std,
                              "estimated_cost_scenarios": self.costs(case, sid, terms, std),
                              "available_claim_cards": available_cards,
                              "previously_used_refs": sorted(self.used_refs),
                              "history": threads[sid]}
                if self.input_version in {"buyer_history", "offer_history"}:
                    state[sid]["buyer_offer_history"] = buyer_offer_history(threads[sid])
                if self.policy == "economics":
                    state[sid]["economic_advice"] = advise(case, self.dossier, sid, terms, std, threads[sid])
                if self.adaptation == "reply_aware":
                    observations[sid] = thread_observations(case, threads[sid], self.decisions, sid)
                    state[sid]["session_observations"] = observations[sid]
                    state[sid]["current_supplier_offers"] = [offer for offer in self.current_offers(case, threads)
                                                             if offer["supplier_id"] == sid]
            if self.policy == "economics":
                record["economic_advice"] = {sid: s["economic_advice"] for sid, s in state.items()}
            user = self.brief + "\nLIVE STATE (estimated supplier financing 12%, cost +/-5%):\n" + encoded(state)
            started = time.monotonic()
            raw = self.model.complete(self.system, user)
            record["model_seconds"] = round(time.monotonic() - started, 3)
            record["model_output"] = raw
            proposal = parse(raw)
            sid = proposal.get("supplier_id")
            if sid not in live_threads(threads):
                raise ValueError("Unknown or inactive supplier")
            forced_decision = None
            if (self.adaptation == "reply_aware" and proposal.get("action") == "send"
                    and observations[sid]["price_freeze_reported"]):
                offers = [offer for offer in self.current_offers(case, threads)
                          if offer["supplier_id"] == sid]
                if offers and isinstance(proposal.get("term_sheets"), list):
                    original = proposal["term_sheets"]
                    retained = [sheet for sheet in original
                                if not is_price_only_cut(case, offers[0]["terms"], sheet)]
                    record["frozen_price_only_sheets_removed"] = len(original) - len(retained)
                    if not retained and original:
                        forced_decision = self.nonprice_counter(case, sid, threads, observations[sid])
                        if not forced_decision:
                            forced_decision = self.safe_close(case, threads)
                        record["freeze_repair"] = forced_decision["message"].get("action", {}).get("type", "send")
                    else:
                        proposal = {**proposal, "term_sheets": retained}
            if proposal.get("action") == "send" and not forced_decision:
                message, validation = render_message(
                    proposal, available_claim_cards(self.cards[sid], self.used_refs,
                    filter_used=self.input_version in {"unused_claims", "offer_history"}),
                    self.used_refs, case, standard_terms(threads[sid]))
                record["validation"] = validation
                # Upstream guard handles round availability and valid IDs; it receives only
                # the already-rendered exact body and strictly validated packages.
                proposal = {"supplier_id": sid, "action": "send", **message}
            body = str((forced_decision or {}).get("message", {}).get("body", proposal.get("body", "")))
            known_offers = {sheet.get("term_sheet_id") for events in threads.values()
                            for sheet in (latest(events).get("term_sheets") or [])}
            if any(not self.fact(case, ref) and ref not in known_offers for ref in ID_RE.findall(body)):
                raise ValueError("Model cited unknown evidence")
            if forced_decision:
                decision = forced_decision
            elif proposal.get("action") in {"accept", "walk_away"}:
                decision = self.safe_close(case, threads)
                record["closing_override"] = decision["message"].get("action", {}).get("type", "send") != \
                    proposal["action"]
            else:
                decision = self.guard(case, threads, proposal)
            if not decision:
                raise ValueError("Invalid model decision")
            msg = decision["message"]
            for sheet in msg.get("term_sheets", []):
                price = sheet["terms"].get("unit_price")
                if not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
                    raise ValueError("Invalid unit price")
                if not must_haves_ok(case, sheet["terms"]):
                    raise ValueError("Proposed terms violate must-haves")
            self.used_refs.update(ID_RE.findall(msg.get("body", "")))
        except Exception as exc:
            self.disabled = True
            decision = self.safe_close(case, threads,
                                       allow_counter="Batch budget exhausted" not in str(exc))
            record.update(fallback=True, reason=str(exc))
        return self.record_decision(record, decision)

    # Strongest first; one fresh checked fact per round (S5: 0 of 9 cases cited anything after round 1,
    # while later replies reacting to a new fact moved 1.2-2.9 % vs 0.15 % without one).
    # S10 reactions: notice and should-cost "took it into account"; past order prices never moved anyone.
    FRESH_PRIORITY = ("notice", "estimate:", "quality", "index:", "forecast:", "delivery")

    @staticmethod
    def forced_claims(events, cards, profile, chosen, fresh=None):
        """Code-selected evidence for profile tactics, whatever the model picks (S6 P01: the model left
        out the contract-notice card; the supplier kept its November start, about EUR 40k for us).
        Saved P01 runs: citing it while asking for a later date won January/April in 27 of 29."""
        chosen = [c for c in (chosen if isinstance(chosen, list) else []) if isinstance(c, str)]
        first = not any(e.get("from") == "buyer" for e in events)
        tactics = {t.get("tactic") for t in profile.get("tactics", [])}
        forced = []
        if first and "defer_effective_date" in tactics and "notice" in cards:
            forced.append("notice")
        # Forcing the supplier-document cards (hedge, open_book) was tested in S8 and not kept: P08 turned
        # the hedge letter into "index clause mandatory" (57.0 vs 67.9); open-book was a no-op on P18/P04.
        latest_body = next((e.get("body") or "" for e in reversed(events) if e.get("from") != "buyer"), "")
        if not first and fresh is not None and (LiveAgent.DATA_QUESTION.search(latest_body)
                                                or LiveAgent.VOLUME_QUESTION.search(latest_body)):
            # Answer "which figures / which volume" with the checked demand forecast, if it is a rise.
            forecast = [k for k in fresh if k.startswith("forecast:") and "change is +" in fresh[k].get("text", "")
                        and not fresh[k]["text"].startswith("The recorded demand forecast change is +0.0")]
            forced += [k for k in forecast[:1] if k not in forced]
        if first and fresh is not None:
            # The first e-mail's three checked arguments, strongest first (S11: the model swapped an
            # index fact for a weaker delivery fact in P08 and its first reply came back higher).
            forced += sorted((k for k in fresh if fresh[k].get("stance") == "buyer_leverage" and k not in forced),
                             key=lambda k: next((i for i, p in enumerate(LiveAgent.FRESH_PRIORITY)
                                                 if k.startswith(p)), 99))
        forced = forced[:3]
        chosen = forced + [c for c in chosen if c not in forced][:3 - len(forced)]
        if fresh is not None and not any(c in fresh for c in chosen) and len(chosen) < 3:
            ranked = sorted((k for k in fresh if fresh[k].get("stance") == "buyer_leverage"), key=lambda k: next(
                (i for i, p in enumerate(LiveAgent.FRESH_PRIORITY) if k.startswith(p)), 99))
            chosen += ranked[:1]
        return chosen

    # Supplier asks for the volume behind our request (traces: "Which volume can you commit to?" 60x in
    # P02, "please provide the specific volume figures" in P02/P03/P04/P07/P10/P18); we never answered.
    VOLUME_QUESTION = re.compile(r"which volume|volume (?:figures|data|projections|planning|basis)|"
                                 r"(?:exact|specific|concrete) volume|volume can you commit|commit to\?|"
                                 r"how many pieces|call-off figures|underlying forecast", re.I)
    # Supplier asks for the data behind our position (P03 "Which figures is that based on? Please send us
    # the data." x14). Codex audit: a checked forecast (volume change) drew "took it into account" 30/38.
    DATA_QUESTION = re.compile(r"which figures|send us the data|data behind|underlying data|figures behind|"
                               r"provide the (?:specific|exact|concrete) (?:volume|data)", re.I)

    @classmethod
    def volume_answer(cls, case, events, terms, proactive=False):
        """One code-rendered sentence with the binding volume of our own term sheets - never a promise
        beyond them - when the supplier's latest e-mail asks for it (or proactively, e.g. an RFQ opening)."""
        latest_body = next((e.get("body") or "" for e in reversed(events) if e.get("from") != "buyer"), "")
        if not (proactive or cls.VOLUME_QUESTION.search(latest_body)) or not terms:
            return []
        fixed = case.get("fixed_terms") or {}
        volumes = {t.get("volume_per_year", fixed.get("volume_per_year")) for t in terms}
        months = {t.get("contract_months", fixed.get("contract_months")) for t in terms}
        if len(volumes) != 1 or None in volumes:
            return []
        volume = volumes.pop()
        need = (case.get("buyer") or {}).get("need_per_year")
        full = ", our full requirement for this part" if isinstance(need, (int, float)) and volume >= need else ""
        lead = "On volume" if proactive else "To answer your question on volume"
        if len(months) == 1 and None not in months:
            m = months.pop()
            return [f"{lead}: each option commits to {volume} units per year for "
                    f"{m} months ({round(volume * m / 12)} units in total){full}."]
        return [f"{lead}: each option commits to {volume} units per year{full}."]

    # Supplier asks to change a term that this case fixes (saved P11 traces: "we really need faster
    # payment" in 133 replies of 33 sessions; payment is fixed at 60 days, our prose never said so).
    FIXED_TERM_REQUEST = {
        "payment_days": re.compile(
            r"(?:faster|earlier|shorter|quicker|sooner|prompter|accelerated) payment|"
            r"payment (?:terms? )?(?:faster|earlier|shorter|sooner)|pay (?:us )?(?:faster|earlier|sooner|quicker)|"
            r"shorten(?:ing)? (?:the )?(?:payment|zahlungsziel)|prepay|advance payment|skonto|early[- ]payment", re.I),
        "contract_months": re.compile(r"(?:longer|shorter) (?:contract|agreement)|extend(?:ing|ed)? the "
                                      r"(?:contract|agreement)|multi-year (?:contract|agreement)", re.I),
        "lead_time_days": re.compile(r"(?:longer|more|extended|relaxed) lead ?time|extend(?:ing)? the lead ?time|"
                                     r"more time (?:for|to) deliver", re.I),
        "effective_date": re.compile(r"(?:earlier|sooner|later) (?:effective|start) date|"
                                     r"(?:bring|move) (?:the )?(?:effective|start) date", re.I),
        "incoterm": re.compile(r"(?:change|switch) (?:the )?(?:incoterm|delivery terms)|ex works instead", re.I),
    }

    @classmethod
    def fixed_term_answer(cls, case, events):
        """Code-rendered statement that a requested term is fixed in this case - never a promise to move
        it - only when the supplier's latest e-mail asks to change a term the case fixes."""
        if not FIXED_TERM_ANSWER:
            return []
        latest_body = next((e.get("body") or "" for e in reversed(events) if e.get("from") != "buyer"), "")
        fixed = case.get("fixed_terms") or {}
        out = []
        for field, pattern in cls.FIXED_TERM_REQUEST.items():
            value = fixed.get(field)
            if field in case.get("negotiable", []) or value is None or not pattern.search(latest_body):
                continue
            if field == "payment_days":
                out.append(f"Payment terms are fixed at {value} days net in this agreement.")
            elif field == "contract_months":
                out.append(f"The contract length is fixed at {value} months in this agreement.")
            elif field == "lead_time_days":
                out.append(f"The lead time is fixed at {value} days in this agreement.")
            elif field == "effective_date":
                out.append(f"The effective date is fixed at {value} in this agreement.")
            elif field == "incoterm":
                out.append(f"The delivery terms are fixed at {value} in this agreement.")
        return out

    ASK_BREAKDOWN = False  # S13: P18 asked, no XLSX and no reaction (58.7 as always); P08 path fixed, untested

    @classmethod
    def asks_breakdown(cls, events, cards):
        """Brief: "a cost breakdown XLSX (ask; an open supplier sends one)". Never received in ~300 saved
        runs: nobody asked the suppliers whose owner offered to walk us through the calculation
        (validation.OPEN_BOOK). Ask once, in the first message; the request line contains "breakdown"."""
        first = not any(e.get("from") == "buyer" for e in events)
        return cls.ASK_BREAKDOWN and first and "open_book" in cards

    def decide_packages(self, case, threads):
        """Send deterministic planner terms; the model chooses only safe message options."""
        record = {"decision": len(self.decisions) + 1, "fallback": False, "policy": "packages"}
        sid = live_threads(threads)[0]  # hosted runner currently admits one supplier only
        events = threads[sid]
        std = standard_terms(events)
        profile = self.profiles[sid]
        display_profile = sourced_profile(profile)
        record["profile"] = display_profile
        if sid in self.pending_alternative and len(events) > self.pending_alternative[sid]["event_count"]:
            decision = self.safe_close(case, threads)
            record["close_reason"] = "alternative_echo_reply"
            return self.record_decision(record, decision)
        try:
            current = self.current_offers(case, {sid: events})
            # A supplier may open outside our must-haves (P10 volume, P11 PPM).
            # That rules out acceptance, but it must not prevent a compliant counter.
            priced = []
            for sheet in latest(events).get("term_sheets") or []:
                terms = sheet.get("terms")
                # A supplier may leave a negotiable field out of both its sheet and its quote (arena
                # `missing_fields`; local P12: no PPM anywhere). The arena still prices such a sheet
                # (cost.closing_terms), so do not give up on it - must-haves are checked at closing.
                if not isinstance(terms, dict):
                    continue
                try:
                    cost = total_cost(case, terms, std)
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
                if math.isfinite(cost):
                    priced.append(sheet)
            if not priced:
                raise ValueError("No priced, completable current supplier sheet")
            plan = plan_packages(case, std, events, profile)
            record["plan"] = plan
            close_reason = ("planner_recommends_accept" if plan["recommend_accept"] else
                            "planner_exhausted" if not plan["packages"] else
                            "agreed" if latest(events).get("status") == "agreed" else
                            "final_offer" if latest(events).get("status") == "final_offer" else
                            "last_buyer_message" if moves_left(case, events) <= 1 else None)
            if close_reason:
                decision = self.safe_close(case, threads)
                record["close_reason"] = close_reason
            else:
                terms = [row["terms"] for row in plan["packages"]]
                if not terms:
                    raise ValueError("Planner returned no packages without recommending acceptance")
                if validate_sheets(case, terms, std) != terms:
                    raise ValueError("Planner packages are invalid or duplicated")
                standing_price = plan["levers"]["base_terms"]["unit_price"]
                threshold = profile.get("approval_threshold_pct")
                documented_approval = (isinstance(threshold, (int, float)) and any(
                    signal.get("kind") == "approval_threshold" and signal.get("ref")
                    for signal in profile.get("signals", [])))
                # A supplier that claims full authority is not asked for approval again (S1 P07).
                documented_approval = documented_approval and not session_signals(events).get("authority_claimed")
                approval_hint = (documented_approval and any(
                    (standing_price - term["unit_price"]) / standing_price * 100 > threshold
                    for term in terms))
                record["approval_hint"] = approval_hint
                cards = available_claim_cards(self.cards[sid], self.used_refs,
                                               filter_used=self.input_version in
                                               {"unused_claims", "offer_history"})
                fresh = available_claim_cards(self.cards[sid], self.used_refs, filter_used=True)
                state = {sid: {"standard_terms": std, "current_supplier_offers": current,
                               "remaining_buyer_messages": moves_left(case, events),
                               "history": events, "plan": plan, "profile": display_profile,
                               "approval_intent_hint": approval_hint,
                               "available_claim_cards": cards,
                               "previously_used_refs": sorted(self.used_refs)}}
                if self.input_version in {"buyer_history", "offer_history"}:
                    state[sid]["buyer_offer_history"] = buyer_offer_history(events)
                try:
                    if self.disabled:
                        raise ValueError("Model disabled after previous error")
                    started = time.monotonic()
                    for attempt in (1, 2):  # S4 P07: one empty reply disabled the model for the session
                        try:
                            raw = self.model.complete(self.system, self.brief + "\nLIVE STATE:\n" + encoded(state))
                            choice = parse(raw)
                            if not isinstance(choice, dict):
                                raise ValueError("Model response is not an object")
                            break
                        except ValueError as exc:
                            if attempt == 2 or "budget" in str(exc).lower() or "limit" in str(exc).lower() \
                                    or time.monotonic() - started > 25:
                                raise
                            record["model_retry"] = str(exc)[:120]
                    record["model_seconds"] = round(time.monotonic() - started, 3)
                    record["model_output"] = raw
                    self.model_failures = 0
                    intent = choice.get("intent", "approval" if approval_hint else "counteroffer")
                    if intent == "approval" and not documented_approval:
                        intent = "counteroffer"
                    if self.asks_breakdown(events, self.cards[sid]):
                        intent = "cost_breakdown"
                    proposal = {"tone": choice.get("tone", "polite"),
                                "intent": intent,
                                "claim_ids": self.forced_claims(events, cards, profile, choice.get("claim_ids", []),
                                                                fresh),
                                "term_sheets": terms}
                    message, validation = render_message(proposal, cards, self.used_refs, case, std)
                    record["validation"] = validation
                    if self.adaptation == "expert_prose":
                        # Figures, claims and terms stay code-rendered; model framing is filtered.
                        answer = self.volume_answer(case, events, terms)
                        record["volume_answer"] = bool(answer)
                        fixed_answer = self.fixed_term_answer(case, events)
                        record["fixed_term_answer"] = bool(fixed_answer)
                        answer += fixed_answer
                        body, prose_diag = compose(
                            case, events, terms, answer + [cards[k]["text"] for k in validation["selected_claims"]],
                            choice, REQUESTS[intent], allow_escalation=intent == "approval",
                            require_request=intent == "cost_breakdown",
                            near_limit=sum(e.get("from") == "buyer" for e in events) >= 3)
                        message["body"] = body
                        record["prose"] = prose_diag
                except Exception as exc:
                    if "Batch budget exhausted" in str(exc):
                        raise  # close safely; do not continue an unpriced session
                    # Switch the model off only after two consecutive failed decisions.
                    self.model_failures = getattr(self, "model_failures", 0) + 1
                    self.disabled = self.model_failures >= 2
                    record.update(fallback=True, reason=f"model: {exc}",
                                  fallback_action="neutral_planned_packages")
                    forced = self.forced_claims(events, cards, profile, [], fresh)
                    message, validation = render_message(
                        {"tone": "polite", "intent": "approval" if approval_hint else "counteroffer",
                         "claim_ids": forced, "term_sheets": terms}, cards if forced else {},
                        self.used_refs, case, std)
                    record["validation"] = validation
                # Do not pass through upstream guard: it may snap valid quote-default values.
                # This body is deterministically rendered and the sheets are validated above.
                if message["term_sheets"] != [{"terms": term} for term in terms]:
                    raise ValueError("Rendered packages differ from the deterministic plan")
                if moves_left(case, events) <= 1:
                    raise ValueError("Round limit reached before planned send")
                decision = {"supplier_id": sid, "message": message}
                self.used_refs.update(message["refs"])
        except Exception as exc:
            decision = self.safe_close(case, threads,
                                       allow_counter="Batch budget exhausted" not in str(exc))
            record.update(fallback=True, reason=f"planner: {exc}",
                          fallback_action="safe_close")
        return self.record_decision(record, decision)


LATE_CHECK_S = 40  # 60 s reply clock per message; past this, re-check the thread before sending


class RecordingTable(RemoteTable):
    def __init__(self, client, folder):
        super().__init__(client)
        self.folder, self.messages = folder, []
        self.replied_at, self.seen = {}, {}  # per supplier: when its last reply arrived, messages seen

    def record(self, who, sid, message):
        self.messages.append({"who": who, "supplier_id": sid, "message": message, "at": round(time.time(), 3)})
        (self.folder / "conversation.json").write_text(json.dumps(self.messages, indent=2) + "\n")
        lines = ["# Hosted practice conversation\n"]
        for i, entry in enumerate(self.messages, 1):
            msg = entry["message"]
            lines += [f"## {i}. {entry['who']} — {entry['supplier_id']}\n", str(msg.get("body", "")),
                      "\n```json\n" + json.dumps({k: v for k, v in msg.items() if k != "body"}, indent=2) + "\n```\n"]
        (self.folder / "conversation.md").write_text("\n".join(lines))
        print(f"{who} {sid}: {message.get('body', message.get('action', message.get('status', '')))}", flush=True)

    def open(self, case_id):
        case, threads = super().open(case_id)
        (self.folder / "session.json").write_text(json.dumps({"session_id": self.session_id, "case_id": case_id}))
        for sid, messages in threads.items():
            for message in messages:
                self.record("Supplier", sid, message)
            self.replied_at[sid], self.seen[sid] = time.monotonic(), len(messages)
        return case, threads

    def send(self, supplier_id, message):
        # S10 P08: our third reply missed the 60 s clock; the arena answered the timeout with a final
        # offer and took our late e-mail as a counter to it - the supplier walked away (score 0).
        # When late, check the thread first; if the supplier has moved on, decide again instead.
        if time.monotonic() - self.replied_at.get(supplier_id, time.monotonic()) > LATE_CHECK_S:
            thread = self.client.thread(self.session_id, supplier_id)
            if thread.get("closed") or len(thread.get("messages") or []) > self.seen.get(supplier_id, 0):
                self.record("Arena (late check)", supplier_id, {"status": thread.get("status"),
                                                                "closed": thread.get("closed")})
                raise ArenaError(409, "late: the supplier answered the timeout; deciding again")
        self.record("Buyer (submitted)", supplier_id, message)
        reply = super().send(supplier_id, message)
        self.record("Supplier", supplier_id, reply)
        self.replied_at[supplier_id] = time.monotonic()
        self.seen[supplier_id] = self.seen.get(supplier_id, 0) + 2
        return reply

    def missed(self, supplier_id, error):
        reply = super().missed(supplier_id, error)
        self.record("Arena (missed)", supplier_id, reply)
        self.replied_at[supplier_id] = time.monotonic()
        self.seen[supplier_id] = len(self.client.thread(self.session_id, supplier_id).get("messages") or [])
        return reply

    def close(self, supplier_id, message):
        self.record("Buyer (submitted)", supplier_id, message)
        result = super().close(supplier_id, message)
        self.record("Result", supplier_id, result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="case:P01")
    parser.add_argument("--variant", choices=VARIANTS, default="evidence_first")
    parser.add_argument("--policy", choices=["current", "economics", "packages"], default="current")
    parser.add_argument("--input-version", choices=["current", "unused_claims", "buyer_history",
                                                   "offer_history"], default="current")
    parser.add_argument("--adaptation", choices=["current", "reply_aware", "expert_prose"], default="current")
    parser.add_argument("--anchor-scale", type=float, default=1.0,
                        help="Scale the goal-based opening ask (packages policy; twin-screened values)")
    parser.add_argument("--llm-model", choices=sorted(PRICES), help="Overrides LLM_MODEL (explicit rollback)")
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high"], default="low",
                        help="Model reasoning effort (same model and token prices; more output tokens)")
    parser.add_argument("--reanchor", type=float, default=0.0,
                        help="One larger step after a stonewalled first reply (0 = off)")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--dossier", type=Path, help="Frozen case context for matched comparisons")
    parser.add_argument("--out", type=Path, help="New run directory, must not already exist")
    parser.add_argument("--batch-start-index", type=int, help="First ledger record in this batch")
    parser.add_argument("--batch-limit-usd", type=float, help="Hard cap on batch model spending")
    parser.add_argument("--run-limit-usd", type=float, default=0.75,
                        help=f"Per-run model cap (explicit override up to {RUN_LIMIT_MAX})")
    parser.add_argument("--total-limit-usd", type=float, default=TOTAL_LIMIT_USD,
                        help="Cumulative ledger cap (raise only with the budget owner's approval)")
    args = parser.parse_args()
    if args.anchor_scale != 1.0 or args.reanchor:
        import nighthunter.packages as planner
        planner.GOAL_MAX_CUT = {k: v * args.anchor_scale for k, v in planner.GOAL_MAX_CUT.items()}
        planner.REANCHOR_STEP = args.reanchor
    load_env(ROOT / ".env")
    if os.environ.get("LLM_PROVIDER") != "openai":
        raise ValueError("This first pilot is configured for OpenAI")
    if os.environ.get("ARENA_URL", "").rstrip("/") != "https://arena.tacto.ai":
        raise ValueError("Unexpected arena URL")
    folder = args.out or ROOT / "artifacts/live" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    folder.mkdir(parents=True, exist_ok=False)
    model = BudgetedModel(ROOT / "artifacts/llm-budget.json", batch_start_index=args.batch_start_index,
                          batch_limit_usd=args.batch_limit_usd, model=args.llm_model,
                          run_limit=args.run_limit_usd, total_limit_usd=args.total_limit_usd)
    model.reasoning_effort = args.reasoning_effort
    model.max_output = 2048 if args.reasoning_effort == "low" else 6144  # room for reasoning tokens
    client = ArenaClient()
    package = DataPackage(DEFAULT_DATA)
    table = None
    try:
        me = client.me()
        if me.get("practice", {}).get("left", 0) <= 0:
            raise ValueError("No practice quota available")
        case = next(c for c in client.cases("practice") if c["case_id"] == args.case and c.get("hosted", True))
        if len(case["suppliers"]) != 1:
            raise ValueError("First live pilot supports a single supplier; RFQ scheduler remains pending")
        dossier = json.loads(args.dossier.read_text()) if args.dossier else CaseContextBuilder().build(case, 40000)
        if dossier["case"] != case:
            raise ValueError("Hosted case changed from frozen comparison context")
        (folder / "dossier.json").write_text(encoded(dossier))
        agent = LiveAgent(model, package, dossier, args.variant, folder, args.policy,
                          args.input_version, args.adaptation)
        metadata = {"case_id": args.case, "model": model.name, "variant": args.variant,
                    "policy": args.policy, "input_version": args.input_version,
                    "adaptation": args.adaptation,
                    "planner_settings": {"anchor_scale": args.anchor_scale, "reanchor": args.reanchor},
                    "economics_sha256": hashlib.sha256((ROOT / "nighthunter/economics.py").read_bytes()).hexdigest(),
                    "context_sha256": hashlib.sha256(encoded(dossier).encode()).hexdigest(),
                    "prompt_sha256": hashlib.sha256(agent.system.encode()).hexdigest(),
                    "shared_prompt_sha256": hashlib.sha256((ROOT / "prompts/common.md").read_bytes()).hexdigest(),
                    "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "validator_sha256": hashlib.sha256((ROOT / "nighthunter/validation.py").read_bytes()).hexdigest(),
                    "model_settings": {"reasoning_effort": args.reasoning_effort, "max_completion_tokens": model.max_output},
                    "prior_best": me.get("best", {}).get(args.case),
                    "limitations": "Structured checked claim cards; model prose not transmitted. "
                                    "Estimated supplier costs/financing; single supplier only."}
        (folder / "metadata.json").write_text(json.dumps(metadata, indent=2))
        print(f"Artifacts: {folder}", flush=True)
        # Fail before consuming a practice session if model/key/endpoint is unavailable.
        probe = model.complete('Return JSON only: {"ready":true}', 'Confirm readiness in JSON.',
                               max_output=128 if model.reasoning_effort == "low" else 2048)
        if not parse(probe).get("ready"):
            raise ValueError("Model preflight did not confirm readiness")
        print("Real model preflight passed.", flush=True)
        if args.preflight_only:
            return
        table = RecordingTable(client, folder)
        started = time.monotonic()
        result = play(table, args.case, agent)
        state = client.session(table.session_id)
        (folder / "state.json").write_text(json.dumps(state, indent=2))
        summary = {**metadata, "session_id": table.session_id, "result": result,
                   "replay_url": state.get("replay_url"), "llm_calls": len(model.records) - model.start,
                   "autonomous_completion": state.get("status") == "ended",
                   "elapsed_seconds": round(time.monotonic() - started, 3),
                   "rounds": state.get("rounds"),
                   "model_seconds": [d.get("model_seconds") for d in agent.decisions],
                   "fallbacks": sum(d["fallback"] for d in agent.decisions),
                   "package_diagnostics": [{"decision": d["decision"], "plan": d.get("plan"),
                                             "profile": d.get("profile"), "close_reason": d.get("close_reason"),
                                             "fallback_action": d.get("fallback_action")}
                                            for d in agent.decisions if d.get("policy") == "packages"],
                   "accounted_usd_upper": sum(r["accounted_usd"] for r in model.records[model.start:])}
        (folder / "summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2), flush=True)
    except Exception as exc:
        (folder / "error.json").write_text(json.dumps({"type": type(exc).__name__, "message": str(exc)}))
        print(f"Run stopped: {type(exc).__name__}: {exc}", flush=True)
        raise SystemExit(1) from None
    finally:
        model.close()
        client.http.close()
        if package.db:
            package.db.close()


if __name__ == "__main__":
    main()
