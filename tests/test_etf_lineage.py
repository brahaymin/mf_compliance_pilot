"""MF-to-ETF tab: lineage plus confirmed ETF fees; only verified links. Synthetic rows only except published-JSON tests."""
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
    assert data["meta"]["fee_status"] == "published"


def test_incomplete_etf_fee_is_not_published():
    data = etf.build(_full(), 2026)
    assert etf.shape_errors(data) == []
    assert "0.03" not in json.dumps(data)
    etf_cls = [c for c in data["rows"][0]["classes"] if c["etf"]][0]
    assert "expense_total" not in etf_cls and "expense_net" not in etf_cls


def test_full_json_link_is_not_published_without_db_row():
    data = etf.build(_full(status="verified"), 2026)
    assert data["rows"][0]["filing"] is None and data["rows"][0]["link_status"] == "none"
    data["rows"][0]["filing"] = {"form": "497K", "date": "2026-01-02", "accession": ACC, "url": "x"}
    data["rows"][0]["link_status"] = "db"
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
        assert data["meta"]["fee_status"] == "published"
    finally:
        db.unlink()


def test_published_json_omits_live_official_file_error_series():
    data = json.loads((ROOT / "etf_lineage.json").read_text(encoding="utf-8"))
    assert data["meta"]["fee_status"] == "published"
    assert data["meta"]["active_series"] == 93
    assert data["meta"]["closed_series"] == 5
    assert data["meta"]["series"] == 98
    assert data["meta"]["hidden_series"] == 5
    assert data["meta"]["links_from_db"] == 84
    assert data["meta"]["links_none"] == 14
    assert data["meta"]["link_source"] == etf.LINK_SOURCE
    assert sum(1 for r in data["rows"] if r["link_status"] == "db" and r["filing"]) == 84
    assert sum(r["filing"] is None for r in data["rows"]) == 14
    if etf.DB_DEFAULT.is_file():
        hidden = etf.load_hidden_series()
        published = {r["series_id"] for r in data["rows"]}
        assert set(hidden).isdisjoint(published)
        assert data["meta"]["hidden_series"] == len(hidden)
        docs = etf.load_primary_documents()
        for r in data["rows"]:
            url = (docs.get(r["series_id"]) or {}).get("source_url") or ""
            if url:
                assert r["link_status"] == "db" and r["filing"]["url"] == url
            else:
                assert r["filing"] is None and r["link_status"] == "none"
        for sid in hidden:
            assert not any(r["series_id"] == sid for r in data["rows"])


DOC = "c497k.htm"
DOC_URL = f"https://www.sec.gov/Archives/edgar/data/1/{ACC.replace('-', '')}/{DOC}"


def _docs_db(rows=None, create_table=True):
    fd, name = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    path = Path(name)
    con = sqlite3.connect(path)
    if create_table:
        con.execute(
            "CREATE TABLE series_primary_document ("
            "series_id TEXT PRIMARY KEY, accession TEXT, primary_document TEXT, "
            "form_type TEXT, filing_date TEXT, source_url TEXT)"
        )
        for row in rows or []:
            con.execute(
                "INSERT INTO series_primary_document "
                "(series_id, accession, primary_document, form_type, filing_date, source_url) "
                "VALUES (?,?,?,?,?,?)",
                row,
            )
        con.commit()
    con.close()
    return path


def test_missing_primary_document_table_publishes_no_links():
    db = _docs_db(create_table=False)
    try:
        assert etf.load_primary_documents(db) == {}
        data = etf.build(_full(), 2026, primary_docs=etf.load_primary_documents(db))
        assert data["rows"][0]["filing"] is None
        assert data["meta"]["links_from_db"] == 0
        assert data["meta"]["links_none"] == 1
        assert etf.shape_errors(data) == []
    finally:
        db.unlink()


def test_db_primary_document_is_published_and_labeled():
    db = _docs_db([
        ("S000000001", ACC, DOC, "497K", "2026-01-02", DOC_URL),
        ("S000000002", None, None, None, None, None),
    ])
    try:
        docs = etf.load_primary_documents(db)
        assert docs["S000000001"]["source_url"] == DOC_URL
        assert docs["S000000002"]["source_url"] == ""
        data = etf.build(_full(status="mismatch"), 2026, primary_docs=docs)
        assert etf.shape_errors(data) == []
        row = data["rows"][0]
        assert row["link_status"] == "db"
        assert row["filing"] == {"form": "497K", "date": "2026-01-02", "accession": ACC, "url": DOC_URL}
        assert data["meta"]["links_from_db"] == 1
        assert data["meta"]["link_source"] == etf.LINK_SOURCE
        assert data["meta"]["fee_status"] == "published"
    finally:
        db.unlink()


def test_blank_primary_document_is_not_invented():
    db = _docs_db([("S000000001", None, None, None, None, None)])
    try:
        data = etf.build(_full(status="verified"), 2026, primary_docs=etf.load_primary_documents(db))
        assert data["rows"][0]["filing"] is None and data["rows"][0]["link_status"] == "none"
        assert data["meta"]["links_from_db"] == 0
        assert etf.shape_errors(data) == []
    finally:
        db.unlink()


def test_hidden_series_omitted_even_with_primary_document():
    qdb = _quality_db([
        ("S000000099", "official_file_error", 2024, "S000000098", "synthetic", "test", "2026-01-01"),
    ])
    ddb = _docs_db([
        ("S000000001", ACC, DOC, "497K", "2026-01-02", DOC_URL),
        ("S000000099", ACC, DOC, "497K", "2026-01-02", DOC_URL.replace("c497k", "other")),
    ])
    try:
        hidden = etf.load_hidden_series(qdb)
        docs = etf.load_primary_documents(ddb)
        f = _full()
        f.append(dict(_full()[0], series_id="S000000099", fund_name="Ghost Fund"))
        data = etf.build(f, 2026, hidden=hidden, primary_docs=docs)
        assert etf.shape_errors(data) == []
        assert [r["series_id"] for r in data["rows"]] == ["S000000001"]
        assert data["meta"]["hidden_series"] == 1
        assert data["rows"][0]["link_status"] == "db"
        assert all(r["series_id"] != "S000000099" for r in data["rows"])
        dumped = json.dumps(data)
        assert "Ghost Fund" not in dumped
        assert DOC_URL.replace("c497k", "other") not in dumped
    finally:
        qdb.unlink()
        ddb.unlink()


def test_complete_etf_fee_is_published_and_mf_fee_is_not():
    fees = {
        "C000000001": {"total": 0.42, "net": 0.41, "accession": ACC, "filing_url": DOC_URL, "form": "497K"},
        "C000000002": {"total": 0.21, "net": 0.18, "accession": ACC, "filing_url": DOC_URL, "form": "497K"},
    }
    data = etf.build(_full(fees=fees), 2026)
    assert etf.shape_errors(data) == []
    by_id = {c["class_id"]: c for c in data["rows"][0]["classes"]}
    mf, etf_cls = by_id["C000000001"], by_id["C000000002"]
    assert "expense_total" not in mf and "expense_net" not in mf
    assert etf_cls["expense_total"] == 0.21 and etf_cls["expense_net"] == 0.18
    assert etf_cls["waiver_amount"] == 0.03
    assert etf_cls["accession"] == ACC and etf_cls["filing_url"] == DOC_URL
    assert etf_cls["source"] == etf.FEE_SOURCE
    dumped = json.dumps(data)
    assert "0.42" not in dumped
    assert data["meta"]["fees_published"] == 1
    assert data["meta"]["fee_status"] == "published"


def test_blank_reason_attached_for_known_class():
    f = _full(fees={})
    f[0]["classes"][1]["class_id"] = "C000275281"
    data = etf.build(f, 2026)
    assert etf.shape_errors(data) == []
    etf_cls = [c for c in data["rows"][0]["classes"] if c["etf"]][0]
    assert etf_cls["reason"] == "not yet effective, no final prospectus"
    assert "expense_total" not in etf_cls and "expense_net" not in etf_cls
    assert data["meta"]["fees_blank"] == 1


def test_published_json_has_confirmed_etf_fees():
    data = json.loads((ROOT / "etf_lineage.json").read_text(encoding="utf-8"))
    assert etf.shape_errors(data) == []
    assert data["meta"]["fee_status"] == "published"
    assert data["meta"]["fees_published"] == 92
    assert data["meta"]["fees_blank"] == 6
    assert data["meta"]["fee_source"] == etf.FEE_SOURCE_META
    published, blank, mf_fees, waivers = 0, 0, 0, 0
    reasons = {}
    for row in data["rows"]:
        for c in row["classes"]:
            if not c.get("etf"):
                if any(k in c for k in ("expense_total", "expense_net", "waiver_amount", "reason")):
                    mf_fees += 1
                continue
            if "expense_total" in c:
                published += 1
                assert isinstance(c["expense_total"], (int, float))
                assert isinstance(c["expense_net"], (int, float))
                assert "reason" not in c
                assert c["source"] == etf.FEE_SOURCE
                assert c["filing_url"].startswith("https://www.sec.gov/Archives/edgar/data/")
                assert c["accession"].replace("-", "") in c["filing_url"]
                w = c.get("waiver_amount")
                if w is not None:
                    assert w > 0
                    assert w == round(c["expense_total"] - c["expense_net"], 2)
                    waivers += 1
                else:
                    assert round(c["expense_total"] - c["expense_net"], 2) == 0
            else:
                blank += 1
                assert c["reason"] in etf.BLANK_REASONS.values()
                assert "expense_total" not in c and "expense_net" not in c and "waiver_amount" not in c
                reasons[c["class_id"]] = c["reason"]
    assert published == 92 and blank == 6 and mf_fees == 0
    assert waivers == 20
    assert reasons["C000275281"] == "not yet effective, no final prospectus"
    assert reasons["C000275282"] == "not yet effective, no final prospectus"
    for cid in ("C000092028", "C000092030", "C000092032", "C000109507"):
        assert reasons[cid] == "older class, no usable fee table in filings"
