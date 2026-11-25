"""MF-to-ETF tab: lineage only, no fee values, only verified links. Synthetic rows only."""
import json
import sys
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
