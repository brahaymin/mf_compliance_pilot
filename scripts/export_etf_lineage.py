#!/usr/bin/env python3
"""Publish the MF-to-ETF supervised-pilot tab data (etf_lineage.json): lineage only.

Reads the local output of mf_compliance scripts/etf_lineage.py (etf_lineage_full.json; never committed)
and writes allowlisted public SEC fields only. Fee values are NEVER written here: fees stay
'pending review' until an independent 20-row blind check passes (<=1 error). A prospectus link is
published only when verified against the fund's own tickers; other links are flagged and omitted.
Shape gate and PII screen run before the published file is replaced; on failure nothing is written.

Usage: python3 scripts/export_etf_lineage.py --full /path/to/etf_lineage_full.json
"""
from __future__ import annotations

import argparse, json, os, re, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pii_screen  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT_NAME = "etf_lineage.json"
ACC = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SERIES = re.compile(r"^S\d{9}$")
URL = re.compile(r"^https://www\.sec\.gov/Archives/edgar/data/\d+/\d{18}/\d{10}-\d{2}-\d{6}-index\.htm$")
FEE_STATUS = "pending review"
ROW_KEYS = {"fund_name", "series_id", "registrant_cik", "classes", "filing", "link_status"}


def build(full: list, source_year) -> dict:
    rows = []
    for r in full:
        verified = str(r.get("link_status", "")).startswith("verified")
        rows.append({
            "fund_name": r.get("fund_name") or r["series_id"],
            "series_id": r["series_id"],
            "registrant_cik": int(r["cik"]),
            "classes": sorted(({"name": c["name"], "ticker": c.get("ticker") or "", "etf": bool(c["etf"])}
                               for c in r["classes"]), key=lambda c: (c["etf"], c["name"])),
            "filing": ({"form": r["form"], "date": r["filing_date"], "accession": r["accession"], "url": r["filing_url"]}
                       if verified else None),
            "link_status": "verified" if verified else ("flagged" if r.get("link_status") in ("mismatch", "file_missing") else "none"),
        })
    rows.sort(key=lambda x: (x["fund_name"].lower(), x["series_id"]))
    meta = {
        "label": "supervised pilot", "fee_status": FEE_STATUS, "source_year": source_year,
        "series": len(rows), "etf_classes": sum(c["etf"] for r in rows for c in r["classes"]),
        "other_classes": sum(not c["etf"] for r in rows for c in r["classes"]),
        "registrants": len({r["registrant_cik"] for r in rows}),
        "links_verified": sum(r["link_status"] == "verified" for r in rows),
        "links_flagged": sum(r["link_status"] == "flagged" for r in rows),
        "scope": "Same portfolio only: a series whose SEC class list has a class named 'ETF Class' or 'ETF Shares' "
                 "alongside mutual fund classes. No 'similar' funds.",
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
    for i, r in enumerate(rows):
        if set(r) != ROW_KEYS: e.append(f"row {i} keys {sorted(set(r) ^ ROW_KEYS)}")
        if not SERIES.match(str(r.get("series_id"))): e.append(f"row {i} series_id")
        cl = r.get("classes") or []
        if sum(c.get("etf") is True for c in cl) < 1 or sum(c.get("etf") is False for c in cl) < 1:
            e.append(f"row {i} needs an ETF class and a fund class")
        for c in cl:
            if set(c) != {"name", "ticker", "etf"}: e.append(f"row {i} class keys")
        f = r.get("filing")
        if r.get("link_status") == "verified":
            if not f or not ACC.match(str(f.get("accession"))) or not URL.match(str(f.get("url"))) \
                    or f["accession"] not in f["url"]:
                e.append(f"row {i} filing link")
        elif f is not None: e.append(f"row {i} unverified link published")
    text = json.dumps(data).lower()
    for banned in ("expense_ratio", "\"fees\"", "\"total\"", "\"net\"", "filing_id", "local_path"):
        if banned in text: e.append(f"banned field {banned}")
    return e


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", required=True)
    ap.add_argument("--out-dir", default=str(REPO))
    a = ap.parse_args(argv)
    full = json.loads(Path(a.full).read_text())
    data = build(full, (full[0].get("source_year") if full else None) or 2026)
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
