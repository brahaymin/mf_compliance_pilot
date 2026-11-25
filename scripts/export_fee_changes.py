#!/usr/bin/env python3
"""Publish the Fee Changes supervised-pilot tab data (fee_changes.json).

Reads the local, sanitized fee-monitor feed (page_feed.csv; never committed)
and writes only confirmed rows with allowlisted public EDGAR fields. Rows
that are unreviewed or rejected, internal ids, and any other columns are
dropped. The shape gate and the PII screen both run on the candidate before
the published file is replaced; on failure nothing is written.

Usage:
  python3 scripts/export_fee_changes.py --feed /path/to/page_feed.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pii_screen  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT_NAME = "fee_changes.json"
FIELDS = (
    "fund_name", "series_id", "field", "old", "new",
    "filing_accession_new", "filing_date_new",
    "filing_accession_prior", "filing_date_prior",
    "form_new", "form_prior", "filing_url_new", "filing_url_prior",
    "fund_type", "ticker", "ticker_source", "doc_url_new", "doc_url_prior",
)


def fund_type(name):
    """Classify from the public fund name only."""
    if not name:
        return "Unclassified"
    return "ETF" if re.search(r"\bETF\b", name) else "Mutual fund"
EDGAR = "https://www.sec.gov/Archives/edgar/data/"


def filing_index_url(accession):
    """EDGAR filing index page for an accession (public; no guessing)."""
    if not ACCESSION.match(accession or ""):
        return None
    return f"{EDGAR}{int(accession.split('-')[0])}/{accession.replace('-', '')}/{accession}-index.htm"
FIELD_LABELS = {
    "total": "Total annual fund operating expenses",
    "net": "Net expenses (after waiver)",
    "other": "Other expenses",
    "waiver": "Fee waiver / expense reimbursement",
    "management": "Management fee",
    "12b1": "Distribution (12b-1) fee",
}
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SERIES = re.compile(r"^S\d{9}$")
DATE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")


class ExportError(SystemExit):
    pass


def shape_errors(data, max_errors=20):
    errors = []
    if not isinstance(data, dict) or not isinstance(data.get("meta"), dict):
        return ["meta missing"]
    meta, rows = data["meta"], data.get("rows")
    if meta.get("label") != "supervised pilot":
        errors.append("meta.label must be 'supervised pilot'")
    if not isinstance(rows, list) or not rows:
        return errors + ["rows missing or empty"]
    if meta.get("row_count") != len(rows):
        errors.append("meta.row_count does not match rows")
    if meta.get("fund_count") != len({r.get("series_id") for r in rows if isinstance(r, dict)}):
        errors.append("meta.fund_count does not match rows")
    for i, r in enumerate(rows):
        if len(errors) >= max_errors:
            break
        if not isinstance(r, dict) or set(r) != set(FIELDS) | {"field_label"}:
            errors.append(f"row {i} has unexpected or missing keys")
            continue
        if not SERIES.match(r["series_id"] or ""):
            errors.append(f"row {i} bad series_id")
        if r["field"] not in FIELD_LABELS:
            errors.append(f"row {i} unknown field")
        if not ACCESSION.match(r["filing_accession_new"] or ""):
            errors.append(f"row {i} bad filing_accession_new")
        if r["filing_url_new"] != filing_index_url(r["filing_accession_new"]):
            errors.append(f"row {i} filing_url_new does not match accession")
        if r["filing_accession_prior"] is not None and (
                not ACCESSION.match(r["filing_accession_prior"])
                or r["filing_url_prior"] != filing_index_url(r["filing_accession_prior"])):
            errors.append(f"row {i} bad prior accession or link")
        for k in ("doc_url_new", "doc_url_prior"):
            if r[k] is not None and not (r[k].startswith(EDGAR) and r[k].endswith(".htm")):
                errors.append(f"row {i} bad {k}")
        for k in ("form_new", "form_prior"):
            if r[k] is not None and not re.match(r"^[0-9A-Z/-]{2,12}$", r[k]):
                errors.append(f"row {i} bad {k}")
        if not DATE.match(r["filing_date_new"] or ""):
            errors.append(f"row {i} bad filing_date_new")
        elif r["filing_date_prior"] is not None and not DATE.match(r["filing_date_prior"]):
            errors.append(f"row {i} bad filing_date_prior")
        elif r["filing_date_new"] < "2020-01-01" or (
                r["filing_date_prior"] is not None and r["filing_date_prior"] >= r["filing_date_new"]):
            errors.append(f"row {i} dates out of order or before 2020")
        for k in ("old", "new"):
            if not isinstance(r[k], (int, float)) or isinstance(r[k], bool):
                errors.append(f"row {i} {k} is not a number")
        if not isinstance(r["fund_name"], str) or not isinstance(r["series_id"], str) or not r["fund_name"].strip():
            errors.append(f"row {i} empty fund_name")
        if r.get("ticker"):
            if r.get("ticker_source") not in ("DB", "SEC"):
                errors.append(f"row {i} ticker missing source label")
        elif r.get("ticker_source") is not None:
            errors.append(f"row {i} ticker_source without ticker")
    return errors


DOCS_FILE = "fee_filing_docs.json"  # accession -> primary doc (Seq 1 on the EDGAR index page)
FORMS_FILE = "fee_filing_forms.json"  # accession -> form type, read from public EDGAR index pages


def load_forms(root=REPO):
    path = Path(root) / FORMS_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


TICKERS_FILE = "fee_class_tickers.json"  # SEC company_tickers_mf.json, matched by series/class ID only
# v1 MF DB, opened read-only. Never write. Used first; SEC file is fallback only.
DB_DEFAULT = Path("/workspace/mf_compliance/data/mf_compliance.db")
_DB_TICKER_CACHE = {}


def load_tickers(root=REPO):
    path = Path(root) / TICKERS_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"series": {}, "classes": {}}


def clean_ticker(value):
    """Drop empty and sentinel values such as the literal '[NULL]'."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"[NULL]", "NULL", "NONE", "N/A"}:
        return None
    return text


def resolve_ticker(series_id, class_id, db_map, sec_classes):
    """Match by series_id + class_contract_id only. DB first, then SEC, else none."""
    series_id = (series_id or "").strip()
    class_id = (class_id or "").strip()
    if not series_id or not class_id:
        return None, None
    ticker = clean_ticker(db_map.get((series_id, class_id)))
    if ticker:
        return ticker, "DB"
    ticker = clean_ticker(sec_classes.get(class_id))
    if ticker:
        return ticker, "SEC"
    return None, None


def series_ticker_entries(series_id, db_map, sec_series):
    """All ID-matched tickers for a series, DB first, then SEC fallback, sorted."""
    seen = set()
    entries = []
    for (sid, _cid), ticker in sorted(db_map.items(), key=lambda kv: (kv[0][0], clean_ticker(kv[1]) or "")):
        if sid != series_id:
            continue
        ticker = clean_ticker(ticker)
        if ticker and ticker not in seen:
            entries.append({"ticker": ticker, "source": "DB"})
            seen.add(ticker)
    for ticker in sec_series.get(series_id, []):
        ticker = clean_ticker(ticker)
        if ticker and ticker not in seen:
            entries.append({"ticker": ticker, "source": "SEC"})
            seen.add(ticker)
    entries.sort(key=lambda e: e["ticker"])
    return entries


def load_db_tickers(series_ids, db_path=None):
    """Read tickers from share_classes then sec_class_years (latest year). mode=ro only."""
    import sqlite3

    path = DB_DEFAULT if db_path is None else (Path(db_path) if db_path else None)
    series_ids = tuple(sorted({s for s in series_ids if s}))
    if not series_ids or path is None or not path.is_file():
        return {}
    cache_key = (str(path.resolve()) if path.exists() else str(path), series_ids)
    if cache_key in _DB_TICKER_CACHE:
        return _DB_TICKER_CACHE[cache_key]
    uri = f"file:{path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        cur = con.cursor()
        placeholders = ",".join("?" * len(series_ids))
        raw = {}
        cur.execute(
            f"""
            SELECT f.series_id, sc.class_contract_id, sc.ticker
            FROM share_classes sc
            JOIN funds f ON f.fund_id = sc.fund_id
            WHERE f.series_id IN ({placeholders})
            """,
            series_ids,
        )
        conflicts = set()
        for series_id, class_id, ticker in cur.fetchall():
            ticker = clean_ticker(ticker)
            if not series_id or not class_id or not ticker:
                continue
            key = (series_id, class_id)
            if key in conflicts:
                continue
            if key in raw and raw[key] != ticker:
                del raw[key]
                conflicts.add(key)
                continue
            raw[key] = ticker
        # Fill remaining keys from the latest sec_class_years row with a ticker.
        cur.execute(
            f"""
            SELECT series_id, class_contract_id, ticker, source_year
            FROM sec_class_years
            WHERE series_id IN ({placeholders})
            ORDER BY source_year DESC
            """,
            series_ids,
        )
        for series_id, class_id, ticker, _year in cur.fetchall():
            ticker = clean_ticker(ticker)
            if not series_id or not class_id or not ticker:
                continue
            key = (series_id, class_id)
            if key not in raw:
                raw[key] = ticker
    finally:
        con.close()
    _DB_TICKER_CACHE[cache_key] = raw
    return raw


def build(feed_path, forms=None, db_path=None):
    forms = load_forms() if forms is None else forms
    with open(feed_path, newline="", encoding="utf-8") as f:
        src = list(csv.DictReader(f))
    rows = []
    for r in src:
        if (r.get("review_status") or "").strip() != "confirmed":
            continue
        out = {k: (r.get(k) or "").strip() or None for k in FIELDS[:9]}
        # Form types and links only from fields present in the feed; missing -> None ("not recorded").
        out["form_new"] = (r.get("form_new") or r.get("form") or "").strip() or forms.get(out["filing_accession_new"])
        out["form_prior"] = (r.get("form_prior") or "").strip() or forms.get(out["filing_accession_prior"])
        out["filing_url_new"] = filing_index_url(out["filing_accession_new"])
        out["filing_url_prior"] = filing_index_url(out["filing_accession_prior"])
        docs = load_forms.__globals__.get("_DOCS")
        if docs is None:
            dp = REPO / DOCS_FILE
            docs = json.loads(dp.read_text(encoding="utf-8")) if dp.is_file() else {}
            globals()["_DOCS"] = docs
        out["doc_url_new"] = docs.get(out["filing_accession_new"] or "")
        out["doc_url_prior"] = docs.get(out["filing_accession_prior"] or "")
        try:
            out["old"], out["new"] = float(out["old"]), float(out["new"])
        except (TypeError, ValueError):
            raise ExportError("non-numeric old/new value in a confirmed row")
        out["fund_type"] = fund_type(out["fund_name"])
        out["_class_id"] = (r.get("class_id") or "").strip()
        out["field_label"] = FIELD_LABELS.get(out["field"], out["field"])
        rows.append(out)
    rows.sort(key=lambda r: (r["filing_date_new"], r["fund_name"], r["field"]), reverse=True)
    tick = load_tickers()
    db_map = load_db_tickers({r["series_id"] for r in rows}, db_path=db_path)
    for out in rows:
        out["ticker"], out["ticker_source"] = resolve_ticker(
            out["series_id"], out.pop("_class_id"), db_map, tick.get("classes") or {})
    series_ids = sorted({r["series_id"] for r in rows})
    return {
        "meta": {
            "label": "supervised pilot",
            "series_tickers": {s: series_ticker_entries(s, db_map, tick.get("series") or {}) for s in series_ids},
            "source": "SEC EDGAR public filings (prospectus fee tables)",
            "units": "percent of net assets, as filed",
            "row_count": len(rows),
            "fund_count": len({r["series_id"] for r in rows}),
            "excluded": {"not_confirmed": len(src) - len(rows)},
            "review": "Each change was checked by hand against the fee tables of both filings "
                      "(58/58 confirmed in the Nov 2026 baseline). Not graded on a random sample.",
            "known_limitation": "Filings without a single Series ID in the header are skipped, and "
                                "one-row horizontal fee tables are missed, so this list is not complete.",
        },
        "rows": rows,
    }


def publish(feed_path, out_dir=REPO, db_path=None):
    data = build(feed_path, db_path=db_path)
    problems = shape_errors(data)
    if problems:
        raise ExportError("fee shape gate failed; not published: " + "; ".join(problems[:5]))
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=out_dir, encoding="utf-8") as tmp:
        tmp.write(text)
    tmp_path = Path(tmp.name)
    hits, _ = pii_screen.scan_json_file(tmp_path)
    if hits:
        tmp_path.unlink()
        raise ExportError("fee PII screen failed; not published: "
                          + json.dumps(pii_screen.summarize(hits), sort_keys=True))
    tmp_path.replace(Path(out_dir) / OUT_NAME)
    return data["meta"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--feed", required=True, help="Local sanitized page_feed.csv (not committed)")
    ap.add_argument("--out-dir", default=str(REPO))
    args = ap.parse_args(argv)
    print(json.dumps(publish(args.feed, Path(args.out_dir)), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
