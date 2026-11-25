"""Fee Changes tab: only confirmed public-EDGAR fields; shape + PII gates.

Synthetic data only (555 test number, fictional funds).
"""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import export_fee_changes as fees  # noqa: E402

HEAD = ["fund_name", "series_id", "class_id", "filing_accession_new", "filing_date_new",
        "filing_accession_prior", "filing_date_prior", "field", "old", "new", "review_status"]


def _row(status="confirmed", **kw):
    r = dict(fund_name="Example Growth Fund", series_id="S000000001", class_id="C000000009",
             filing_accession_new="0000000000-26-000002", filing_date_new="2026-11-05",
             filing_accession_prior="0000000000-25-000001", filing_date_prior="2025-11-01",
             field="total", old="1.10", new="0.95", review_status=status)
    r.update(kw)
    return r


def _feed(tmp_path, rows):
    p = tmp_path / "page_feed.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEAD)
        w.writeheader()
        w.writerows(rows)
    return p


def test_published_fee_json_passes_gates():
    data = json.loads((ROOT / "fee_changes.json").read_text(encoding="utf-8"))
    assert fees.shape_errors(data) == []
    assert data["meta"]["label"] == "supervised pilot"
    for r in data["rows"]:
        assert set(r) == set(fees.FIELDS) | {"field_label"}
    text = json.dumps(data)
    for banned in ("filing_id", "class_id", "review_status", "unreviewed"):
        assert banned not in text


def test_only_confirmed_rows_exported(tmp_path):
    feed = _feed(tmp_path, [_row(), _row("unreviewed", field="net"), _row("rejected", field="other")])
    meta = fees.publish(feed, tmp_path)
    data = json.loads((tmp_path / "fee_changes.json").read_text())
    assert meta["row_count"] == 1 and meta["excluded"]["not_confirmed"] == 2
    assert [r["field"] for r in data["rows"]] == ["total"]
    assert "class_id" not in data["rows"][0]


def test_pii_blocks_publish(tmp_path):
    (tmp_path / "fee_changes.json").write_text("{}")
    feed = _feed(tmp_path, [_row(fund_name="Call 212-555-0100 Fund")])
    with pytest.raises(SystemExit) as exc:
        fees.publish(feed, tmp_path)
    assert "fee PII screen failed; not published" in str(exc.value)
    assert (tmp_path / "fee_changes.json").read_text() == "{}"
    assert list(tmp_path.glob("tmp*.json")) == []


def test_bad_shape_blocks_publish(tmp_path):
    (tmp_path / "fee_changes.json").write_text("{}")
    feed = _feed(tmp_path, [_row(series_id="not-a-series")])
    with pytest.raises(SystemExit) as exc:
        fees.publish(feed, tmp_path)
    assert "fee shape gate failed; not published" in str(exc.value)
    assert (tmp_path / "fee_changes.json").read_text() == "{}"


def test_no_raw_fee_sources_in_repo():
    for pattern in ("page_feed*.csv", "baseline*.csv", "review_*.csv"):
        assert not list(ROOT.rglob(pattern)), pattern


def test_rows_link_exact_filings_and_mark_missing_prior(tmp_path):
    feed = _feed(tmp_path, [_row(), _row(field="net", filing_accession_prior="", filing_date_prior="")])
    fees.publish(feed, tmp_path)  # synthetic accessions are not in the forms map
    rows = json.loads((tmp_path / "fee_changes.json").read_text())["rows"]
    by = {r["field"]: r for r in rows}
    assert by["total"]["filing_url_new"] == (
        "https://www.sec.gov/Archives/edgar/data/0/000000000026000002/0000000000-26-000002-index.htm")
    assert by["total"]["filing_url_prior"].endswith("0000000000-25-000001-index.htm")
    assert by["total"]["form_new"] is None  # feed has no form column -> "not recorded"
    assert by["net"]["filing_accession_prior"] is None and by["net"]["filing_url_prior"] is None


def test_form_types_come_from_edgar_map_only():
    forms = json.loads((ROOT / "fee_filing_forms.json").read_text(encoding="utf-8"))
    data = json.loads((ROOT / "fee_changes.json").read_text(encoding="utf-8"))
    for r in data["rows"]:
        assert r["form_new"] == forms.get(r["filing_accession_new"])
        assert r["form_prior"] == forms.get(r["filing_accession_prior"])


def test_fund_type_split_labels_and_newest_first():
    data = json.loads((ROOT / "fee_changes.json").read_text(encoding="utf-8"))
    rows = data["rows"]
    assert len(rows) == 58
    assert sum(r["fund_type"] == "Mutual fund" for r in rows) == 42
    assert sum(r["fund_type"] == "ETF" for r in rows) == 16
    assert fees.fund_type("") == "Unclassified" and fees.fund_type("X Bond Fund") == "Mutual fund"
    dates = [r["filing_date_new"] for r in rows]
    assert dates == sorted(dates, reverse=True)
    js = (ROOT / "fees.js").read_text(encoding="utf-8")
    assert 'filter.value = "all"' in js and "type-badge" in js and 'data-type' in js


def test_tickers_never_guessed_and_search_present():
    rows = json.loads((ROOT / "fee_changes.json").read_text(encoding="utf-8"))["rows"]
    assert all(r["ticker"] is None for r in rows)  # no ticker source today
    js = (ROOT / "fees.js").read_text(encoding="utf-8")
    assert '"no ticker"' in js and "feesSearch" in js and "data-search" in js
