"""Deterministic, bounded buyer context. No model, credentials or network access."""

import argparse
import csv
import hashlib
import json
import os
import sqlite3
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "vendor/negotiation-arena-kit/data"
# Sunday release (new letters, news, memo; new IDs only), unpacked outside vendor/. Brief: hidden cases may
# cite it; practice cases stay on package v1 - so its rows enter only non-practice dossiers (see build).
DEFAULT_RELEASE = ROOT / "data/release-sunday"
if (DEFAULT_RELEASE / "facts.json").is_file():
    os.environ.setdefault("ARENA_RELEASE", str(DEFAULT_RELEASE))  # DataPackage merges its facts
ALIASES = {"sup:71999": "sup:70210"}  # data/KNOWN_ISSUES.md, item 5
PRIORITY = [
    "suppliers", "parts", "contracts", "contract_clauses", "documents", "supplier_intel",
    "should_cost", "scorecards", "news", "sourcing", "cost_drivers", "index_series",
    "index_values", "quotes", "negotiation_history", "price_conditions", "forecasts",
    "rfqs", "spend_cube", "po_lines", "invoices", "quality_notifications", "goods_receipts",
    "forecast_lines",
]
DATES = ("date", "quarter", "month", "snapshot_month", "estimate_date", "quote_date",
         "valid_from", "order_date", "invoice_date", "qn_date", "posting_date", "fiscal_year")


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ContextBudgetError(ValueError):
    """The exact case and essential evidence cannot fit the requested budget."""


class CaseContextBuilder:
    def __init__(self, data=DEFAULT_DATA, release=DEFAULT_RELEASE if (DEFAULT_RELEASE / "facts.json").is_file()
                 else None):
        self.root = Path(data).resolve()
        self.release = Path(release).resolve() if release else None
        self.facts = json.loads((self.root / "facts.json").read_text())
        self.release_rows, self.release_ids = {}, set()
        if self.release:
            extra = json.loads((self.release / "facts.json").read_text())
            self.release_ids = set(extra)
            duplicates = self.facts.keys() & extra.keys()
            if duplicates:
                raise ValueError("Supplemental release reuses existing fact IDs")
            self.facts.update(extra)
            for path in sorted((self.release / "data").glob("*.csv")):
                with path.open(newline="") as stream:
                    self.release_rows[path.stem] = list(csv.DictReader(stream))

    def build(self, case, max_chars=60000):
        """Bound serialized JSON characters, not model tokens; fail if essentials overflow."""
        for field in ("case_id", "buyer", "suppliers", "parts", "negotiable", "fixed_terms"):
            if field not in case:
                raise ValueError(f"Missing required case field: {field}")
        suppliers = set(case["suppliers"])
        suppliers |= {ALIASES.get(s, s) for s in suppliers}
        suppliers |= {old for old, new in ALIASES.items() if new in suppliers}
        parts = set(case["parts"])
        required_refs = set(case.get("refs", []))
        if case.get("trigger_doc"):
            required_refs.add(case["trigger_doc"])
        facts = {**self.facts, **case.get("facts", {})}
        # Practice cases stay on package v1 unless the case itself cites a release ID.
        use_release = case.get("set") not in {"practice", "sandbox"} or bool(required_refs & self.release_ids)
        rows = {}
        # Read-only SQL. Only fixed, internal table names are used in SQL identifiers.
        with sqlite3.connect(f"file:{self.root / 'world.sqlite'}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            for table in PRIORITY:
                rows[table] = [dict(r) for r in db.execute(f'SELECT * FROM "{table}"')]
                if use_release:
                    rows[table] += self.release_rows.get(table, [])

        selected = {}
        for table, values in rows.items():
            selected[table] = []
            for row in values:
                sid = row.get("supplier_id")
                pid = row.get("part_id")
                direct = row.get("id") in required_refs
                match = False
                if table == "suppliers":
                    match = row["id"] in suppliers
                elif table == "parts":
                    match = row["id"] in parts
                elif table in {"sourcing", "should_cost", "quotes"}:
                    match = pid in parts  # preserve alternative sources and benchmarks
                elif sid and pid:
                    match = sid in suppliers and pid in parts
                elif sid:
                    match = sid in suppliers
                elif pid:
                    match = pid in parts
                if match or direct:
                    selected[table].append(row)
        contracts = {r["id"] for r in selected["contracts"]}
        forecasts = {r["id"] for r in selected["forecasts"]}
        series = {r["series_id"] for r in selected["cost_drivers"]}
        series |= {r["series"] for r in rows["contract_clauses"]
                   if r["contract_id"] in contracts and r.get("series")}
        for table, column, keys in [
            ("contract_clauses", "contract_id", contracts), ("forecast_lines", "fc_id", forecasts),
            ("index_series", "id", series), ("index_values", "series_id", series),
        ]:
            selected[table] = [r for r in rows[table] if r.get(column) in keys or r.get("id") in required_refs]

        warnings, evidence, seen = [], [], set()
        for table, requested in (("suppliers", set(case["suppliers"])), ("parts", parts)):
            available = {row["id"] for row in selected[table]}
            for ref in sorted(requested - available):
                warnings.append(f"Missing identity record: {ref}")
        for table in PRIORITY:
            values = sorted(selected[table], key=lambda r: (
                next((str(r[d]) for d in DATES if r.get(d)), ""), encoded(r)), reverse=True)
            for row in values:
                ref = row.get("id")
                identity = f"{table}:{ref or hashlib.sha256(encoded(row).encode()).hexdigest()[:16]}"
                if identity in seen:
                    raise ValueError(f"Duplicate source identity: {identity}")
                seen.add(identity)
                source_root = self.release if row in self.release_rows.get(table, []) else self.root
                entry = {"source": identity, "table": table, "row": row,
                         "origin": "release" if source_root == self.release else "base",
                         "citable_fact": facts.get(ref) if ref else None}
                if table in {"documents", "contracts"} and row.get("file"):
                    path = (source_root / row["file"]).resolve()
                    if path.is_relative_to(source_root) and path.is_file():
                        entry["document"] = path.read_text()
                    else:
                        warnings.append(f"Missing or unsafe document: {identity}")
                essential = table in {"suppliers", "parts", "contracts", "contract_clauses"} or ref in required_refs
                evidence.append((essential, entry))

        found_refs = {e["row"].get("id") for _, e in evidence}
        for ref in sorted(required_refs | set(case.get("facts", {}))):
            if ref in facts and ref not in found_refs:
                evidence.insert(0, (True, {"source": ref, "table": "case_refs", "row": facts[ref],
                                          "citable_fact": facts[ref],
                                          "origin": "case" if ref in case.get("facts", {}) else "facts.json"}))
        missing = sorted(ref for ref in required_refs if ref not in facts and ref not in found_refs)
        coverage = {t: {"found": len(selected[t]), "included": 0, "omitted": len(selected[t])} for t in PRIORITY}
        result = {
            "case": case, "supplier_aliases": {k: v for k, v in ALIASES.items() if k in suppliers},
            "evidence": [], "coverage": coverage, "unresolved_refs": missing, "warnings": warnings,
            "pending": ["Read supplier opening quote, standard terms and attachments after session opens"],
            "budget": {"max_chars": max_chars, "unit": "serialized JSON characters, not tokens"},
            "omitted_evidence": 0,
            "limitations": "Retrieved rows are evidence, not hidden supplier floors. Historical contracts require "
                            "validity review. Look up omitted sources again. Claims need separate numeric validation.",
        }

        def add(entry):
            result["evidence"].append(entry)
            if entry["table"] in coverage:
                coverage[entry["table"]]["included"] += 1
                coverage[entry["table"]]["omitted"] -= 1

        for essential, entry in evidence:
            if essential:
                add(entry)
        if len(encoded(result)) > max_chars:
            raise ContextBudgetError("Case, required refs, identities and contracts exceed context budget")
        # Balance categories so a long index/history table cannot crowd out quotes or quality.
        # Required references bypass these optional-history limits.
        groups = defaultdict(deque)
        per_series = Counter()
        for essential, entry in evidence:
            if not essential:
                table = entry["table"]
                if table == "index_values":
                    series_id = entry["row"]["series_id"]
                    if per_series[series_id] >= 13:
                        continue
                    per_series[series_id] += 1
                elif len(groups[table]) >= 12:
                    continue
                groups[table].append(entry)
        while any(groups.values()):
            for group in groups.values():
                if not group:
                    continue
                entry = group.popleft()
                # Reserve counter space; never slice a document or JSON mid-record.
                if len(encoded(result)) + len(encoded(entry)) + 128 <= max_chars:
                    add(entry)
        result["omitted_evidence"] = len(evidence) - len(result["evidence"])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, type=Path, help="Case JSON (local or downloaded)")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--release", type=Path)
    parser.add_argument("--max-chars", type=int, default=60000)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    case = json.loads(args.case.read_text())
    dossier = CaseContextBuilder(args.data, args.release).build(case, args.max_chars)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(encoded(dossier) + "\n")
    counts = Counter(e["table"] for e in dossier["evidence"])
    print(json.dumps({"case_id": case["case_id"], "characters": len(encoded(dossier)),
                      "included_by_table": dict(counts), "omitted": dossier["omitted_evidence"],
                      "unresolved_refs": dossier["unresolved_refs"], "warnings": dossier["warnings"]}, indent=2))


if __name__ == "__main__":
    main()
