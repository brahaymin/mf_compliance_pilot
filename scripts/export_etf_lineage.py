#!/usr/bin/env python3
"""Publish the MF-to-ETF supervised-pilot tab data (etf_lineage.json).

Reads the local output of mf_compliance scripts/etf_lineage.py (etf_lineage_full.json; never committed)
and writes allowlisted public SEC fields only. Expense ratios (Total and Net, plus a
waiver amount when above 0) are published for each active share class — ETF and sister
classes — when both figures are present, along with the exact Total/Net filing lines and a
deep link to that class's fee table. Inactive classes are omitted. The two non-effective
TCW ETF classes stay blank with the existing reason.
A prospectus link is published only from series_primary_document in the v1 DB (read-only) when
that row has a source_url; blank or missing rows stay unlinked. Shape gate and PII screen run
before the published file is replaced; on failure nothing is written.

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
CLASS_ID = re.compile(r"^C\d{9}$")
# Primary-document URL (exact document, not an EDGAR index page), optional text-fragment highlight.
URL = re.compile(
    r"^https://www\.sec\.gov/Archives/edgar/data/\d+/\d{18}/[A-Za-z0-9._-]+\.htm(?:#:~:text=.+)?$"
)
FEE_STATUS = "published"
FEE_SOURCE = "v1 MF DB"
FEE_SOURCE_META = "v1 MF DB, accession"
ROW_KEYS = {"status", "last_seen", "fund_name", "series_id", "registrant_cik", "classes", "filing", "link_status", "source"}
CLASS_REQUIRED = {"name", "ticker", "etf", "active", "last_year"}
CLASS_OPTIONAL = {
    "class_id", "expense_total", "expense_net", "waiver_amount",
    "accession", "filing_url", "source", "form", "reason",
    "total_line", "net_line",
}
# CEO-specified reasons for the six ETF classes with no published fee (run9).
BLANK_REASONS = {
    "C000275281": "not yet effective, no final prospectus",
    "C000275282": "not yet effective, no final prospectus",
    "C000092028": "older class, no usable fee table in filings",
    "C000092030": "older class, no usable fee table in filings",
    "C000092032": "older class, no usable fee table in filings",
    "C000109507": "older class, no usable fee table in filings",
}
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


def etf_fee_fields(fee) -> dict | None:
    """Allowlisted ETF fee fields from a full-file fee record. Both figures required."""
    if not isinstance(fee, dict) or fee.get("total") is None or fee.get("net") is None:
        return None
    total, net = fee["total"], fee["net"]
    if not isinstance(total, (int, float)) or not isinstance(net, (int, float)):
        return None
    url = (fee.get("filing_url") or "").split("#", 1)[0].strip()
    frag = (fee.get("filing_url_fragment") or fee.get("text_fragment") or "").strip()
    if frag and not frag.startswith("#"):
        frag = "#" + frag
    out = {
        "expense_total": total,
        "expense_net": net,
        "accession": fee.get("accession"),
        "filing_url": url + frag,
        "source": FEE_SOURCE,
    }
    if fee.get("form"):
        out["form"] = fee["form"]
    line = (fee.get("total_line") or "").strip()
    if line:
        out["total_line"] = line
    # Exact Net line only when the filing has an after-waiver line; never invent one.
    if fee.get("waiver_line") and not fee.get("net_defaulted"):
        net_line = (fee.get("net_line") or "").strip()
        if net_line:
            out["net_line"] = net_line
    waiver = round(total - net, 2)
    if waiver > 0:
        out["waiver_amount"] = waiver
    return out


def _public_class(c, year, fees_map) -> dict:
    item = {
        "name": c["name"],
        "ticker": c.get("ticker") or "",
        "etf": bool(c["etf"]),
        "active": c.get("last_year", year) == year,
        "last_year": c.get("last_year", year),
    }
    cid = c.get("class_id")
    if cid:
        item["class_id"] = cid
    # Fees for any current-year class, and for an ETF class on a closed series.
    # Inactive sister classes are not published (they are omitted from the row).
    if cid and (item["active"] or item["etf"]):
        fields = etf_fee_fields((fees_map or {}).get(cid))
        if fields:
            item.update(fields)
        elif item["etf"] and cid in BLANK_REASONS:
            item["reason"] = BLANK_REASONS[cid]
    return item


def _keep_class(c, year, series_active, last_seen) -> bool:
    """Current-year classes always; ETF classes always; last-seen fund class on a closed series."""
    if c.get("last_year", year) == year:
        return True
    if c.get("etf"):
        return True
    return (not series_active) and c.get("last_year") == last_seen


def _fee_counts(rows):
    published = blank = 0
    for r in rows:
        for c in r["classes"]:
            if "expense_total" in c and "expense_net" in c:
                published += 1
            elif c.get("reason"):
                blank += 1
    return published, blank


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
        last_seen = min(max(c.get("last_year", year) for c in r["classes"] if c["etf"]),
                        max(c.get("last_year", year) for c in r["classes"] if not c["etf"]))
        filing = _filing_from_db(primary_docs.get(r["series_id"]))
        kept = [c for c in r["classes"] if _keep_class(c, year, active, last_seen)]
        rows.append({
            "status": "active" if active else "closed",
            "last_seen": last_seen,
            "fund_name": r.get("fund_name") or r["series_id"],
            "series_id": r["series_id"],
            "registrant_cik": int(r["cik"]),
            "classes": sorted((_public_class(c, year, r.get("fees") or {}) for c in kept),
                              key=lambda c: (c["etf"], c["name"])),
            "filing": filing,
            "source": SOURCE,
            "link_status": "db" if filing else "none",
        })
    rows.sort(key=lambda x: (x["fund_name"].lower(), x["series_id"]))
    fees_published, fees_blank = _fee_counts(rows)
    fees_published_active, fees_blank_active = _fee_counts([r for r in rows if r["status"] == "active"])
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
        "hidden_series": len(hidden) if hidden else omitted,
        "hide_source": HIDE_SOURCE,
        "hide_rule": "Every series with series_data_quality.flag = official_file_error is omitted; not a hardcoded list.",
        "fees_published": fees_published,
        "fees_blank": fees_blank,
        "fees_published_active": fees_published_active,
        "fees_blank_active": fees_blank_active,
        "fee_source": FEE_SOURCE_META,
    }
    return {"meta": meta, "rows": rows}


def _class_errors(i, c) -> list:
    e = []
    keys = set(c)
    if not CLASS_REQUIRED <= keys or (keys - CLASS_REQUIRED - CLASS_OPTIONAL):
        e.append(f"row {i} class keys")
        return e
    cid = c.get("class_id")
    if cid is not None and not CLASS_ID.match(str(cid)):
        e.append(f"row {i} class_id")
    has_fee = "expense_total" in c or "expense_net" in c
    has_reason = "reason" in c
    if has_fee and has_reason:
        e.append(f"row {i} fee and reason")
    if has_fee:
        if not c.get("active") and not c.get("etf"):
            e.append(f"row {i} fee on inactive class")
        if not isinstance(c.get("expense_total"), (int, float)) or not isinstance(c.get("expense_net"), (int, float)):
            e.append(f"row {i} fee numbers")
        waiver = c.get("waiver_amount")
        if waiver is not None and (not isinstance(waiver, (int, float)) or waiver <= 0):
            e.append(f"row {i} waiver")
        acc = str(c.get("accession") or "")
        url = str(c.get("filing_url") or "")
        base = url.split("#", 1)[0]
        if (not ACC.match(acc) or not URL.match(url) or acc.replace("-", "") not in url
                or base.lower().endswith("-index.htm") or base.lower().endswith("-index.html")):
            e.append(f"row {i} fee filing link")
        if c.get("source") != FEE_SOURCE:
            e.append(f"row {i} fee source")
        if not (c.get("total_line") or "").strip():
            e.append(f"row {i} total_line")
        if "net_line" in c:
            if not str(c.get("net_line") or "").strip():
                e.append(f"row {i} empty net_line")
        elif c.get("waiver_amount"):
            e.append(f"row {i} waiver missing net_line")
    if has_reason:
        if not c.get("etf"):
            e.append(f"row {i} reason on mutual fund class")
        if c.get("reason") not in BLANK_REASONS.values():
            e.append(f"row {i} reason text")
        if any(k in c for k in ("expense_total", "expense_net", "waiver_amount", "accession", "filing_url")):
            e.append(f"row {i} blank has fee fields")
    return e


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
    published, blank = _fee_counts(rows)
    if m.get("fees_published") != published: e.append("meta.fees_published")
    if m.get("fees_blank") != blank: e.append("meta.fees_blank")
    pub_a, blank_a = _fee_counts([r for r in rows if r.get("status") == "active"])
    if m.get("fees_published_active") not in (None, pub_a): e.append("meta.fees_published_active")
    if m.get("fees_blank_active") not in (None, blank_a): e.append("meta.fees_blank_active")
    if m.get("fee_source") != FEE_SOURCE_META: e.append("meta.fee_source")
    for i, r in enumerate(rows):
        if set(r) != ROW_KEYS: e.append(f"row {i} keys {sorted(set(r) ^ ROW_KEYS)}")
        if r.get("status") not in ("active", "closed") or not isinstance(r.get("last_seen"), int): e.append(f"row {i} status")
        if not SERIES.match(str(r.get("series_id"))): e.append(f"row {i} series_id")
        cl = r.get("classes") or []
        if sum(c.get("etf") is True for c in cl) < 1 or sum(c.get("etf") is False for c in cl) < 1:
            e.append(f"row {i} needs an ETF class and a fund class")
        for c in cl:
            e.extend(_class_errors(i, c))
        f = r.get("filing")
        if r.get("link_status") == "db":
            acc = str((f or {}).get("accession") or "")
            url = str((f or {}).get("url") or "")
            if not f or not ACC.match(acc) or not URL.match(url) or acc.replace("-", "") not in url:
                e.append(f"row {i} filing link")
        elif f is not None:
            e.append(f"row {i} link published without a DB primary document")
    text = json.dumps(data).lower()
    for banned in ("filing_id", "local_path"):
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
