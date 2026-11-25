#!/usr/bin/env python3
"""Publish the MF-to-ETF supervised-pilot tab data (etf_lineage.json): lineage only.

Reads the local output of mf_compliance scripts/etf_lineage.py (etf_lineage_full.json; never committed)
and writes allowlisted public SEC fields only. Fee values are NEVER written here: fees stay
'pending review' until an independent 20-row blind check passes (<=1 error). A prospectus link is
published only from series_primary_document in the v1 DB (read-only) when that row has a source_url;
blank or missing rows stay unlinked. Shape gate and PII screen run before the published file is
replaced; on failure nothing is written.

Usage: python3 scripts/export_etf_lineage.py --full /path/to/etf_lineage_full.json
"""
from __future__ import annotations

import argparse, json, os, re, sqlite3, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pii_screen  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT_NAME = "etf_lineage.json"
ACC = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SERIES = re.compile(r"^S\d{9}$")
# Primary-document URL from series_primary_document (not an EDGAR index page).
URL = re.compile(
    r"^https://www\.sec\.gov/Archives/edgar/data/\d+/\d{18}/[A-Za-z0-9._-]+\.htm$"
)
FEE_STATUS = "pending review"
ROW_KEYS = {"status", "last_seen", "fund_name", "series_id", "registrant_cik", "classes", "filing", "link_status", "source"}
SOURCE = (
    "v1 MF DB (read-only): sec_class_years classes/tickers; "
    "series_primary_document for the prospectus/primary-document link; "
    "series_data_quality (flag=official_file_error) to omit official-file-error series"
)
LINK_SOURCE = "v1 MF DB (read-only): series_primary_document"
HIDE_FLAG = "official_file_error"
HIDE_SOURCE = "v1 MF DB (read-only): series_data_quality.flag = official_file_error"
DB_DEFAULT = Path("/workspace/mf_compliance/data/mf_compliance.db")


def _open_ro(db_path=None):
    path = Path(db_path) if db_path is not None else DB_DEFAULT
    if not path or not path.is_file():
        return None, None
    con = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    return path, con


def load_hidden_series(db_path=None) -> dict:
    """Map series_id -> flag row for official_file_error. Missing table or DB => {}."""
    path, con = _open_ro(db_path)
    if con is None:
        return {}
    try:
        try:
            rows = con.execute(
                "SELECT series_id, flag, source_year, live_series_id, note, provenance, recorded_at "
                "FROM series_data_quality WHERE flag = ?",
                (HIDE_FLAG,),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower() or "no such column" in str(exc).lower():
                return {}
            raise
        out = {}
        for series_id, flag, source_year, live_series_id, note, provenance, recorded_at in rows:
            if series_id:
                out[str(series_id)] = {
                    "flag": flag,
                    "source_year": source_year,
                    "live_series_id": live_series_id,
                    "note": note,
                    "provenance": provenance,
                    "recorded_at": recorded_at,
                }
        return out
    finally:
        con.close()


def load_primary_documents(db_path=None) -> dict:
    """Map series_id -> series_primary_document row. Missing table or DB => {}."""
    path, con = _open_ro(db_path)
    if con is None:
        return {}
    try:
        try:
            rows = con.execute(
                "SELECT series_id, accession, primary_document, form_type, filing_date, source_url "
                "FROM series_primary_document"
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower() or "no such column" in str(exc).lower():
                return {}
            raise
        out = {}
        for series_id, accession, primary_document, form_type, filing_date, source_url in rows:
            if series_id:
                out[str(series_id)] = {
                    "accession": accession,
                    "primary_document": primary_document,
                    "form_type": form_type,
                    "filing_date": filing_date,
                    "source_url": (source_url or "").strip(),
                }
        return out
    finally:
        con.close()


def _filing_from_db(doc) -> dict | None:
    url = (doc or {}).get("source_url") or ""
    if not url:
        return None
    return {
        "form": doc.get("form_type"),
        "date": doc.get("filing_date"),
        "accession": doc.get("accession"),
        "url": url,
    }


def build(full: list, source_year, hidden=None, primary_docs=None) -> dict:
    hidden = hidden or {}
    primary_docs = primary_docs or {}
    rows = []
    year = max(c.get("last_year", source_year) for r in full for c in r["classes"]) if full else source_year
    omitted = 0
    for r in full:
        if r["series_id"] in hidden:
            omitted += 1
            continue
        cur = [c for c in r["classes"] if c.get("last_year", year) == year]
        active = any(c["etf"] for c in cur) and any(not c["etf"] for c in cur)
        filing = _filing_from_db(primary_docs.get(r["series_id"]))
        rows.append({
            "status": "active" if active else "closed",
            "last_seen": min(max(c.get("last_year", year) for c in r["classes"] if c["etf"]),
                             max(c.get("last_year", year) for c in r["classes"] if not c["etf"])),
            "fund_name": r.get("fund_name") or r["series_id"],
            "series_id": r["series_id"],
            "registrant_cik": int(r["cik"]),
            "classes": sorted(({"name": c["name"], "ticker": c.get("ticker") or "", "etf": bool(c["etf"]),
                                "active": c.get("last_year", year) == year, "last_year": c.get("last_year", year)}
                               for c in r["classes"]), key=lambda c: (c["etf"], c["name"])),
            "filing": filing,
            "source": SOURCE,
            "link_status": "db" if filing else "none",
        })
    rows.sort(key=lambda x: (x["fund_name"].lower(), x["series_id"]))
    meta = {
        "label": "supervised pilot", "source": SOURCE, "outside_sources": "none used", "fee_status": FEE_STATUS, "source_year": source_year,
        "series": len(rows), "active_series": sum(r["status"] == "active" for r in rows),
        "closed_series": sum(r["status"] == "closed" for r in rows),
        "status_rule": "Active: the SEC class list for the latest year still shows an ETF class and a mutual fund class. "
                       "Closed: last seen together in an earlier year (last seen year shown).", "etf_classes": sum(c["etf"] for r in rows for c in r["classes"]),
        "other_classes": sum(not c["etf"] for r in rows for c in r["classes"]),
        "registrants": len({r["registrant_cik"] for r in rows}),
        "links_from_db": sum(r["link_status"] == "db" for r in rows),
        "links_none": sum(r["link_status"] != "db" for r in rows),
        "link_source": LINK_SOURCE,
        "scope": "Same portfolio only: a series whose SEC class list has a class named 'ETF Class' or 'ETF Shares' "
                 "alongside mutual fund classes. No 'similar' funds.",
        "hidden_series": omitted,
        "hide_source": HIDE_SOURCE,
        "hide_rule": "Every series with series_data_quality.flag = official_file_error is omitted; not a hardcoded list.",
    }
    return {"meta": meta, "rows": rows}


def shape_errors(data) -> list:
    e = []
    m = data.get("meta", {})
    if m.get("label") != "supervised pilot": e.append("meta.label")
    if m.get("fee_status") != FEE_STATUS: e.append("meta.fee_status")
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows: return e + ["rows empty"]
    if m.get("series") != len(rows): e.append("meta.series count")
    if m.get("links_from_db") != sum(r.get("link_status") == "db" for r in rows): e.append("meta.links_from_db")
    if m.get("links_none") != sum(r.get("link_status") != "db" for r in rows): e.append("meta.links_none")
    for i, r in enumerate(rows):
        if set(r) != ROW_KEYS: e.append(f"row {i} keys {sorted(set(r) ^ ROW_KEYS)}")
        if r.get("status") not in ("active", "closed") or not isinstance(r.get("last_seen"), int): e.append(f"row {i} status")
        if not SERIES.match(str(r.get("series_id"))): e.append(f"row {i} series_id")
        cl = r.get("classes") or []
        if sum(c.get("etf") is True for c in cl) < 1 or sum(c.get("etf") is False for c in cl) < 1:
            e.append(f"row {i} needs an ETF class and a fund class")
        for c in cl:
            if set(c) != {"name", "ticker", "etf", "active", "last_year"}: e.append(f"row {i} class keys")
        f = r.get("filing")
        if r.get("link_status") == "db":
            acc = str((f or {}).get("accession") or "")
            url = str((f or {}).get("url") or "")
            if not f or not ACC.match(acc) or not URL.match(url) or acc.replace("-", "") not in url:
                e.append(f"row {i} filing link")
        elif f is not None:
            e.append(f"row {i} link published without a DB primary document")
    text = json.dumps(data).lower()
    for banned in ("expense_ratio", "\"fees\"", "\"total\"", "\"net\"", "filing_id", "local_path"):
        if banned in text: e.append(f"banned field {banned}")
    return e


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", required=True)
    ap.add_argument("--out-dir", default=str(REPO))
    ap.add_argument("--db", default=str(DB_DEFAULT),
                    help="v1 MF DB path, opened read-only. Missing table is treated as zero flags and zero links.")
    a = ap.parse_args(argv)
    full = json.loads(Path(a.full).read_text())
    hidden = load_hidden_series(a.db)
    primary_docs = load_primary_documents(a.db)
    data = build(full, (full[0].get("source_year") if full else None) or 2026,
                 hidden=hidden, primary_docs=primary_docs)
    errs = shape_errors(data)
    if errs:
        print("shape gate failed: " + "; ".join(errs[:20]), file=sys.stderr); return 2
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=a.out_dir, encoding="utf-8") as t:
        json.dump(data, t, indent=1, ensure_ascii=False); t.write("\n"); tmp = t.name
    hits, _ = pii_screen.scan_json_file(tmp)
    if hits:
        os.unlink(tmp); print("PII screen failed: " + json.dumps(pii_screen.summarize(hits)), file=sys.stderr); return 3
    os.replace(tmp, Path(a.out_dir) / OUT_NAME)
    print(json.dumps(data["meta"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
