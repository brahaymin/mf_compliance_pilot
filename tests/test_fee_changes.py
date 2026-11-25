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
    data = json.loads((ROOT / "fee_changes.json").read_text(encoding="utf-8"))
    tick = json.loads((ROOT / "fee_class_tickers.json").read_text(encoding="utf-8"))
    sec_allowed = set(tick["classes"].values())
    for r in data["rows"]:
        if r["ticker"] is None:
            assert r["ticker_source"] is None
        else:
            assert r["ticker_source"] in ("DB", "SEC")
            if r["ticker_source"] == "SEC":
                assert r["ticker"] in sec_allowed
    js = (ROOT / "fees.js").read_text(encoding="utf-8")
    assert '"no ticker"' in js and "feesSearch" in js and "data-search" in js
    assert "ticker-source" in js


def test_rows_link_primary_documents_from_edgar_map():
    docs = json.loads((ROOT / "fee_filing_docs.json").read_text(encoding="utf-8"))
    rows = json.loads((ROOT / "fee_changes.json").read_text(encoding="utf-8"))["rows"]
    for r in rows:
        assert r["doc_url_new"] == docs[r["filing_accession_new"]]
        assert r["doc_url_prior"] == docs[r["filing_accession_prior"]]
        assert r["doc_url_new"].startswith(fees.EDGAR) and r["filing_accession_new"].replace("-", "") in r["doc_url_new"]
    js = (ROOT / "fees.js").read_text(encoding="utf-8")
    assert "index-link" in js and "Annual%20Fund%20Operating%20Expenses" in js


def test_tickers_db_first_then_sec_and_labeled():
    data = json.loads((ROOT / "fee_changes.json").read_text(encoding="utf-8"))
    for entries in data["meta"]["series_tickers"].values():
        assert isinstance(entries, list)
        seen = set()
        for e in entries:
            assert e["source"] in ("DB", "SEC") and e["ticker"] and e["ticker"] not in seen
            seen.add(e["ticker"])
        assert entries == sorted(entries, key=lambda e: e["ticker"])
    # All nine fund cards have at least one DB ticker after the N-CEN fill.
    labeled = [e for entries in data["meta"]["series_tickers"].values() for e in entries]
    assert sum(1 for entries in data["meta"]["series_tickers"].values() if entries) == 9
    assert all(e["source"] == "DB" for e in labeled)
    assert "class_id" not in json.dumps(data)


def test_resolve_ticker_db_first_id_only_and_null_sentinel():
    db_map = {("S000000001", "C000000009"): "DBAAA", ("S000000001", "C000000010"): "[NULL]"}
    sec = {"C000000009": "SECAA", "C000000011": "SECBB", "C000000010": "SECCC"}
    assert fees.resolve_ticker("S000000001", "C000000009", db_map, sec) == ("DBAAA", "DB")
    assert fees.resolve_ticker("S000000001", "C000000011", db_map, sec) == ("SECBB", "SEC")
    assert fees.resolve_ticker("S000000001", "C000000010", db_map, sec) == ("SECCC", "SEC")
    assert fees.resolve_ticker("S000000002", "C000000009", db_map, sec) == ("SECAA", "SEC")
    assert fees.resolve_ticker("S000000001", "", db_map, sec) == (None, None)
    assert fees.clean_ticker("[NULL]") is None
    # Series list: DB tickers first, SEC only for gaps, no name matching required.
    entries = fees.series_ticker_entries("S000000001", {("S000000001", "C000000009"): "DBAAA"},
                                         {"S000000001": ["DBAAA", "SECBB"]})
    assert entries == [{"ticker": "DBAAA", "source": "DB"}, {"ticker": "SECBB", "source": "SEC"}]


def test_load_db_tickers_prefers_share_classes_over_sec_years(tmp_path):
    import sqlite3
    db = tmp_path / "mini.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE funds (fund_id INTEGER PRIMARY KEY, series_id TEXT, fund_name TEXT);
        CREATE TABLE share_classes (
            class_id INTEGER PRIMARY KEY, fund_id INTEGER, class_name TEXT,
            ticker TEXT, class_contract_id TEXT
        );
        CREATE TABLE sec_class_years (
            class_contract_id TEXT, source_year INTEGER, series_id TEXT, ticker TEXT,
            PRIMARY KEY (class_contract_id, source_year)
        );
        INSERT INTO funds VALUES (1, 'S000000001', 'Example Growth Fund');
        INSERT INTO share_classes VALUES (1, 1, 'Class A', 'DBAAA', 'C000000009');
        INSERT INTO share_classes VALUES (2, 1, 'Legacy', '[NULL]', 'C000000009');
        INSERT INTO sec_class_years VALUES ('C000000009', 2026, 'S000000001', 'OLDYZ');
        INSERT INTO sec_class_years VALUES ('C000000012', 2026, 'S000000001', 'YEARX');
        """
    )
    con.commit()
    con.close()
    got = fees.load_db_tickers(["S000000001"], db_path=db)
    assert got[("S000000001", "C000000009")] == "DBAAA"
    assert got[("S000000001", "C000000012")] == "YEARX"
    assert "[NULL]" not in got.values()
