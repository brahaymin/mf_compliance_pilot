"""MF-to-ETF tab: lineage only, no fee values, only verified links. Synthetic rows only."""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import export_etf_lineage as etf  # noqa: E402

ACC = "0000000000-26-000001"


def _full(status="verified", fees=None):
    return [{"series_id": "S000000001", "cik": 1, "fund_name": "Example Index Fund", "source_year": 2026,
             "classes": [{"class_id": "C000000001", "name": "Admiral Shares", "ticker": "EXAMX", "etf": False, "last_year": 2026},
                         {"class_id": "C000000002", "name": "ETF Shares", "ticker": "EXE", "etf": True, "last_year": 2026}],
             "link_status": status, "form": "497K", "filing_date": "2026-01-02", "accession": ACC,
             "filing_url": f"https://www.sec.gov/Archives/edgar/data/1/{ACC.replace('-', '')}/{ACC}-index.htm",
             "fees": fees or {"C000000002": {"total": 0.03}}}]


def test_published_json_passes_gates():
    data = json.loads((ROOT / "etf_lineage.json").read_text(encoding="utf-8"))
    assert etf.shape_errors(data) == []
    assert data["meta"]["fee_status"] == "pending review"


def test_fees_never_published():
    data = etf.build(_full(), 2026)
    assert etf.shape_errors(data) == []
    assert "0.03" not in json.dumps(data)


def test_unverified_link_is_not_published():
    data = etf.build(_full(status="mismatch"), 2026)
    assert data["rows"][0]["filing"] is None and data["rows"][0]["link_status"] == "flagged"
    data["rows"][0]["filing"] = {"form": "497K", "date": "2026-01-02", "accession": ACC, "url": "x"}
    assert etf.shape_errors(data)


def test_etf_page_links_open_new_tab():
    js = (ROOT / "etf.js").read_text(encoding="utf-8")
    assert 'n.target = "_blank"' in js and 'n.rel = "noopener"' in js


def test_closed_series_labeled():
    f = _full()
    f[0]["classes"][1]["last_year"] = 2024
    f.append(dict(_full()[0], series_id="S000000002"))
    data = etf.build(f, 2026)
    assert etf.shape_errors(data) == []
    st = {r["series_id"]: (r["status"], r["last_seen"]) for r in data["rows"]}
    assert st == {"S000000001": ("closed", 2024), "S000000002": ("active", 2026)}
    assert data["meta"]["active_series"] == 1 and data["meta"]["closed_series"] == 1


def _quality_db(rows=None, create_table=True):
    fd, name = tempfile.mkstemp(suffix=".db")
    Path(name)  # keep path
    import os
    os.close(fd)
    path = Path(name)
    con = sqlite3.connect(path)
    if create_table:
        con.execute(
            "CREATE TABLE series_data_quality ("
            "series_id TEXT PRIMARY KEY, flag TEXT NOT NULL, source_year INTEGER, "
            "live_series_id TEXT, note TEXT, provenance TEXT NOT NULL, recorded_at TEXT NOT NULL)"
        )
        for row in rows or []:
            con.execute("INSERT INTO series_data_quality VALUES (?,?,?,?,?,?,?)", row)
        con.commit()
    con.close()
    return path


def test_missing_quality_table_hides_nothing():
    db = _quality_db(create_table=False)
    try:
        assert etf.load_hidden_series(db) == {}
        data = etf.build(_full(), 2026, hidden=etf.load_hidden_series(db))
        assert [r["series_id"] for r in data["rows"]] == ["S000000001"]
        assert data["meta"]["hidden_series"] == 0
    finally:
        db.unlink()


def test_official_file_error_series_are_omitted():
    db = _quality_db([
        ("S000000099", "official_file_error", 2024, "S000000098", "synthetic", "test", "2026-01-01"),
        ("S000000001", "other_flag", 2024, None, "keep", "test", "2026-01-01"),
    ])
    try:
        hidden = etf.load_hidden_series(db)
        assert set(hidden) == {"S000000099"}
        assert hidden["S000000099"]["flag"] == "official_file_error"
        f = _full()
        f.append(dict(_full()[0], series_id="S000000099", fund_name="Ghost Fund"))
        data = etf.build(f, 2026, hidden=hidden)
        assert etf.shape_errors(data) == []
        assert [r["series_id"] for r in data["rows"]] == ["S000000001"]
        assert data["meta"]["hidden_series"] == 1
        assert data["meta"]["series"] == 1
        assert data["meta"]["hide_source"] == etf.HIDE_SOURCE
        assert data["meta"]["fee_status"] == "pending review"
    finally:
        db.unlink()


def test_published_json_omits_live_official_file_error_series():
    data = json.loads((ROOT / "etf_lineage.json").read_text(encoding="utf-8"))
    assert data["meta"]["fee_status"] == "pending review"
    assert data["meta"]["active_series"] == 93
    assert data["meta"]["closed_series"] == 5
    assert data["meta"]["series"] == 98
    assert data["meta"]["hidden_series"] == 5
    if etf.DB_DEFAULT.is_file():
        hidden = etf.load_hidden_series()
        published = {r["series_id"] for r in data["rows"]}
        assert set(hidden).isdisjoint(published)
        assert data["meta"]["hidden_series"] == len(hidden)
