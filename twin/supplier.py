"""A behavioural supplier twin calibrated on hosted transcripts (twin.calibrate, twin.anchor).

The twin negotiates in its own value terms (arena_kit.cost.supplier_value at an assumed 8 % rate):
- its reservation is the best value it could get from any package costing the buyer C_best;
- first reply: concedes a share of its room that depends on how deep our first ask is (anchoring
  sweet spot ~1.0-1.5x its room; a far deeper ask is stonewalled);
- later: mirrors our concessions (share `mirror`), freezes on token steps, issues final_offer after
  its patience or two stalls, and may walk away if countered after a final offer;
- answers "agreed" with our best package for it when that meets its current position.
Offline evaluation only. It is a model of behaviour, not the hosted supplier: use it to screen
strategies, then confirm on hosted practice cases.
"""

import math
import random
from dataclasses import dataclass, field

from arena_kit.cost import closing_terms, supplier_value

SELLER_RATE = 0.08

# Reaction to a NEW verified fact, by type: chance of "we did not know that - a fair point" (280
# post-session traces, ours + teammate, 2026-10-11). A fair point moved later-round prices 1.84 % vs
# 0.75 % without an evidence reaction; FAIR_BONUS converts that ~1.1 pt into a share of the room.
FAIR_PROB = {"notice": 0.9, "rival": 0.37, "should_cost": 0.6, "delivery": 0.18, "quality": 0.05,
             "volume": 0.1, "index": 0.03, "price_history": 0.0}
FAIR_BONUS = 0.07
# S9: answering the first big drop with a much smaller step made the supplier RAISE its price ~1 %.
UNMATCHED_SHARE, UNMATCHED_RAISE = 0.5, 0.009

# Persona ranges per goal from the calibration quartiles (first_share, mirror, final_at).
PERSONAS = {  # recalibrated on ~200 hosted transcripts (ours + teammate), 2026-10-10 night
    # stonewall (depth of our first ask / its room beyond which it barely moves): hosted S3 lost with
    # anchors at 1.42x (P18) and 1.48x (P03) while 0.9-1.3x worked; L17: stabilise moves 62 % of room
    # at 1.0-1.5x vs 16 % beyond. Recalibrated 2026-10-11 so the twin reproduces S3 (L24).
    "stabilise": {"first": (0.18, 0.64), "mirror": (0.0, 0.61), "patience": (3, 5), "stonewall": (1.3, 1.6),
                  "slack": (0.0, 0.025)},
    "leverage": {"first": (0.23, 0.55), "mirror": (0.27, 1.2), "patience": (3, 4), "stonewall": (1.35, 1.6),
                 "slack": (0.0, 0.01)},
    "routine": {"first": (0.18, 0.80), "mirror": (0.0, 0.82), "patience": (3, 4), "stonewall": (2.5, 6.0),
                "slack": (0.0, 0.007)},
    "secure_supply": {"first": (0.05, 0.10), "mirror": (0.2, 0.8), "patience": (2, 2), "stonewall": (1.2, 1.8),
                      "slack": (0.0, 0.003)},
    "quality_first": {"first": (0.00, 0.16), "mirror": (0.0, 1.0), "patience": (4, 6), "stonewall": (1.2, 1.8),
                      "slack": (0.0, 0.01)},
}


@dataclass
class Persona:
    first: float
    mirror: float
    patience: int
    stonewall: float
    stall_threshold: float = 0.05
    walk_prob: float = 0.5
    # How much the supplier weighs the cash effect of non-price terms (payment, start date) against
    # unit price: 0 = price only, 1 = full cash value. Hosted evidence: P01 granted an April start
    # (~EUR 5/unit to it) for +0.35; P04 granted 90-day payment and cut price; P02 charged ~75 % of
    # the value of longer payment. Sampled per game.
    term_weight: float = 0.5
    # Hidden acceptance line below the stated position, as a share of opening value. Measured on 46
    # hosted "agreed" events: stabilise suppliers agreed a median 0.75 % (max 3.3 %) below their last
    # stated price; leverage/routine/secure ~0 % median.
    accept_slack: float = 0.0
    gap_follow: float = 0.8   # first reply never concedes more than this share of the gap we opened

    @classmethod
    def sample(cls, goal, rng):
        p = PERSONAS.get(goal, PERSONAS["stabilise"])
        return cls(first=rng.uniform(*p["first"]), mirror=rng.uniform(*p["mirror"]),
                   patience=rng.randint(*p["patience"]), stonewall=rng.uniform(*p["stonewall"]),
                   term_weight=rng.uniform(0.0, 0.8), accept_slack=rng.uniform(*p["slack"]))


@dataclass
class SupplierTwin:
    case: dict
    standard: dict
    opening: dict          # complete opening terms
    c_best: float          # offline benchmark: places the twin's reservation
    persona: Persona
    rng: random.Random
    real_ppm: float = None
    sid: str = "sup:twin"
    history: list = field(default_factory=list)

    def __post_init__(self):
        self.seller = {"standard": closing_terms(self.case, {}, self.standard), "interest_rate": SELLER_RATE}
        if self.real_ppm is not None:
            self.seller["ppm"] = self.real_ppm  # chargebacks cost the twin at its scorecard defect rate
        self.v0 = self.position = self.value(self.opening)
        self.floor_value = self.reservation()
        self.room = max(self.v0 - self.floor_value, 1e-9)
        self.terms, self.round, self.stalls, self.final, self.last_ours = dict(self.opening), 0, 0, False, None
        self.status, self.walked = "open", False

    def value(self, terms):
        """Perceived value: unit price on its opening terms plus a weighted cash effect of other terms."""
        base = supplier_value(self.case, {**self.opening, "unit_price": terms["unit_price"]}, self.seller)
        return base + self.persona.term_weight * (supplier_value(self.case, terms, self.seller) - base)

    def reservation(self):
        """Best perceived value among packages costing the buyer exactly C_best."""
        from nighthunter.packages import compositions, price_for_cost
        best = None
        for comp in compositions(self.case, self.standard):
            price = price_for_cost(self.case, self.standard, comp, self.c_best)
            if price:
                v = self.value({**comp, "unit_price": price})
                best = v if best is None else max(best, v)
        return min(best, self.v0) if best is not None else self.v0

    def price_for_value(self, comp, target):
        v1, v2 = self.value({**comp, "unit_price": 1.0}), self.value({**comp, "unit_price": 2.0})
        return math.ceil((1.0 + (target - v1) / (v2 - v1)) * 100) / 100

    def message(self, status, terms):
        self.status, self.terms = status, terms
        self.history.append((status, dict(terms)))
        return {"from": "sales", "status": status, "body": "",
                "term_sheets": [{"term_sheet_id": f"offer:twin-{self.round}", "terms": dict(terms)}]}

    def opening_message(self):
        return self.message("open", self.opening)

    def respond(self, sheets, claims=()):
        """claims: types of the new verified facts cited in this buyer message (FAIR_PROB keys)."""
        self.round += 1
        if self.final:  # countered after a final offer
            if self.rng.random() < self.persona.walk_prob:
                self.walked = True
                return {"from": "sales", "status": "walked_away", "body": "", "term_sheets": []}
            return self.message("final_offer", self.terms)
        best_value, best = max(((self.value(t), t) for t in sheets), key=lambda x: x[0])
        line = max(self.floor_value, self.position - self.persona.accept_slack * self.v0)
        if best_value >= line - 1e-6 * self.v0:
            self.position = best_value
            return self.message("agreed", best)
        if self.round == 1:
            depth = (self.v0 - best_value) / self.room
            share = self.persona.first if depth <= self.persona.stonewall else 0.15 * self.persona.first
            concession = min(share * self.room, self.persona.gap_follow * (self.position - best_value))
            self.first_concession = concession
        else:
            our_move = best_value - self.last_ours if self.last_ours is not None else 0.0
            gap = self.position - (self.last_ours if self.last_ours is not None else best_value)
            if gap <= 0 or our_move < self.persona.stall_threshold * gap:
                self.stalls += 1
                concession = 0.0
            else:
                concession = self.persona.mirror * our_move
            if self.round == 2 and our_move < UNMATCHED_SHARE * getattr(self, "first_concession", 0.0):
                concession = -UNMATCHED_RAISE * self.v0  # its big first drop went unanswered
        for kind in claims:
            if self.rng.random() < FAIR_PROB.get(kind, 0.0):
                concession += FAIR_BONUS * self.room
        self.last_ours = best_value
        self.position = min(self.v0, max(self.floor_value, self.position - concession))
        if self.position - best_value <= 0.002 * self.v0:  # close enough: take our package
            self.position = best_value
            return self.message("agreed", best)
        comp = {k: v for k, v in best.items() if k != "unit_price"}
        terms = {**comp, "unit_price": self.price_for_value(comp, self.position)}
        if self.round >= self.persona.patience or self.stalls >= 2:
            self.final = True
            return self.message("final_offer", terms)
        return self.message("open", terms)
