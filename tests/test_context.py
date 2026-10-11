import json
from copy import deepcopy

import pytest

from nighthunter.context import DEFAULT_DATA, ROOT, CaseContextBuilder, ContextBudgetError, encoded
from nighthunter.experiment import prepare


@pytest.fixture
def case():
    path = ROOT / "vendor/negotiation-arena-kit/starter-kit/arena_kit/sim_cases/S01.json"
    return json.loads(path.read_text())


@pytest.fixture
def builder():
    return CaseContextBuilder()


def test_required_context_is_exact_and_budgeted(builder, case):
    result = builder.build(case)
    assert result["case"] == case
    assert len(encoded(result)) <= 60000
    assert not result["unresolved_refs"]
    assert any(e["table"] == "contracts" and e.get("document") for e in result["evidence"])
    assert all(c["found"] == c["included"] + c["omitted"] for c in result["coverage"].values())
    assert result["pending"]  # opening quote cannot be known before opening
    assert builder.build(case) == result


def test_budget_never_silently_removes_essential_records(builder, case):
    with pytest.raises(ContextBudgetError):
        builder.build(case, max_chars=100)
    result = builder.build(case, max_chars=16000)
    assert len(encoded(result)) <= 16000
    assert result["omitted_evidence"] > 0
    for ref in case["refs"]:
        assert any(e["source"] == ref or e["row"].get("id") == ref for e in result["evidence"])


def test_missing_ref_is_explicit(builder, case):
    case["refs"].append("doc:missing")
    assert builder.build(case)["unresolved_refs"] == ["doc:missing"]


def test_unknown_supplier_is_not_reported_as_complete(builder, case):
    case["suppliers"] = ["sup:unknown"]
    result = builder.build(case)
    assert "Missing identity record: sup:unknown" in result["warnings"]
    assert result["coverage"]["contracts"]["found"] == 0


def test_erp_price_unit_is_preserved(builder, case):
    case["parts"] = ["part:340020"]
    result = builder.build(case)
    part = next(e["row"] for e in result["evidence"] if e["table"] == "parts")
    assert part["price_unit"] == 100
    assert result["case"]["buyer"] == case["buyer"]


def test_case_fact_overrides_base_without_mutation(builder, case):
    ref = case["refs"][0]
    original = deepcopy(builder.facts[ref])
    case["facts"][ref] = {"supplier": "sup:70270", "ppm": 1234}
    result = builder.build(case)
    record = next(e for e in result["evidence"] if e["row"].get("id") == ref)
    assert record["citable_fact"]["ppm"] == 1234
    assert builder.facts[ref] == original


def test_alias_and_supplier_contracts(builder, case):
    case["suppliers"] = ["sup:71999"]
    result = builder.build(case)
    assert result["supplier_aliases"] == {"sup:71999": "sup:70210"}
    assert any(e["table"] == "suppliers" and e["row"]["id"] == "sup:70210" for e in result["evidence"])
    assert any(e["table"] == "contracts" and e["row"]["supplier_id"] == "sup:70210"
               for e in result["evidence"])


def test_relationship_note_and_trigger_are_retrieved(builder, case):
    case["suppliers"] = ["sup:70110"]
    case["parts"] = ["part:310010"]
    case["trigger_doc"] = "doc:20260911-70110-P01"
    result = builder.build(case)
    texts = "\n".join(e.get("document", "") for e in result["evidence"])
    assert "2022" in texts and "partnership" in texts
    assert "9.5" in texts


def test_supplemental_document_is_searchable(tmp_path, case):
    (tmp_path / "data").mkdir()
    (tmp_path / "correspondence").mkdir()
    (tmp_path / "facts.json").write_text(json.dumps({"doc:new": {"supplier": "sup:70270"}}))
    (tmp_path / "data/documents.csv").write_text(
        "id,supplier_id,date,file\ndoc:new,sup:70270,2026-10-01,correspondence/new.md\n")
    (tmp_path / "correspondence/new.md").write_text("New capacity becomes available.")
    case["trigger_doc"] = "doc:new"
    result = CaseContextBuilder(DEFAULT_DATA, tmp_path).build(case)
    item = next(e for e in result["evidence"] if e["row"].get("id") == "doc:new")
    assert item["origin"] == "release"
    assert item["document"] == "New capacity becomes available."


def test_prompt_comparison_holds_context_constant(builder, case):
    rows = prepare(case, builder)
    assert len(rows) == 4
    assert len({r["context_sha256"] for r in rows}) == 1
    assert len({r["prompt_sha256"] for r in rows}) == 4
    assert all("must-have" in row["system"] for row in rows)
