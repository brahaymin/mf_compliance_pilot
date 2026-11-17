#!/usr/bin/env python3
"""Export sanitized, static data slices for the MF Feedback Pilot site.

The live database is opened read-only only (SQLite URI mode=ro and
PRAGMA query_only=ON). This script never writes the database, never
reads .env or identity files, and never touches HOLD, STOP, processes,
or data/backups.

Default outputs (written under --out-dir):
  * coverage_slices.json — aggregated public-filing counts by year,
    form type, and fund family, plus compact structured-rule coverage
    counts (the pilot's proposed UI view rollups, as data, not as
    CREATE VIEW on the live database).
  * family_contacts.json — existing pilot view, with phone, e-mail,
    and address values dropped (aggregate/count + source filing only).
    Allowlisted institutional websites may be kept.

Existing sample views (structured_rules_sample.json, sample_rules.json,
priorities_demo_stats.json, priorities_ideas.json, issue_map.json) are
PII-screened and included in the size budget. They are not rebuilt from
the full library by default: a full structured-rules export of every
family would exceed the static-site size cap. Pass --structured-exporter
to optionally rebuild structured_rules_sample.json with the private
pipeline exporter.

The run is deterministic for a given database snapshot: JSON is written
with sorted keys and no wall-clock timestamp. Freshness is the latest
filing_date and a sha256 of the aggregate payload.

Usage:
  python3 scripts/refresh_pilot_data.py --db /path/to/mf_compliance.db
  python3 scripts/refresh_pilot_data.py --db FILE --out-dir DIR
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pii_screen  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

RAW_LIMIT = 25 * 1000 * 1000  # 25 MB, decimal, matching the static-site cap
GZIP_LIMIT = 3 * 1000 * 1000  # 3 MB gzipped

DATA_FILES = (
    "coverage_slices.json",
    "family_contacts.json",
    "structured_rules_sample.json",
    "sample_rules.json",
    "priorities_demo_stats.json",
    "priorities_ideas.json",
    "issue_map.json",
)

# Institutional fund sites already allowlisted by family-contacts.js.
ALLOWED_SITE_HOSTS = frozenset({
    "fidelity.com",
    "www.fidelity.com",
    "institutional.fidelity.com",
    "401k.com",
    "www.401k.com",
    "guggenheiminvestments.com",
    "www.guggenheiminvestments.com",
    "naafunds.com",
    "www.naafunds.com",
})

DROPPED_CONTACT_TYPES = frozenset({"phone", "email", "address"})


class RefreshError(SystemExit):
    """Fatal refresh failure (non-zero exit)."""


def open_readonly(path):
    """Open SQLite at path in URI mode=ro with query_only=ON."""
    db = Path(path).expanduser().resolve()
    if not db.is_file():
        raise RefreshError(f"database not found: {db}")
    # Never open the sidecar WAL/SHM ourselves; SQLite will read them
    # if present. Do not set journal_mode (a bare PRAGMA journal_mode
    # can be a write on some builds).
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def count_or_none(conn, name):
    if not table_exists(conn, name):
        return None
    return int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])


def fetchall(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params)]


def dump_json(path, obj):
    """Deterministic JSON: sorted keys, compact separators, trailing newline."""
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    Path(path).write_text(text + "\n", encoding="utf-8")


def allowed_website(value):
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme != "https":
        return None
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_SITE_HOSTS:
        return None
    # Origin only; drop paths that might carry session or personal tokens.
    return f"https://{host}/"


def sanitize_family_contacts(data):
    """Drop individual contact details; keep counts and public filing cites."""
    if not isinstance(data, dict):
        raise RefreshError("family_contacts.json must be an object")
    dropped = Counter()
    kept_sites = 0
    families_out = []
    for fam in data.get("families") or []:
        groups_out = []
        for group in fam.get("groups") or []:
            entries_out = []
            for entry in group.get("entries") or []:
                kind = (entry.get("type") or "").lower()
                out = {
                    "accession": entry.get("accession"),
                    "edgar_url": entry.get("edgar_url"),
                    "filing_date": entry.get("filing_date"),
                    "form_type": entry.get("form_type"),
                    "label": entry.get("label"),
                    "published_in_filing": True,
                    "type": entry.get("type"),
                }
                if kind == "website":
                    site = allowed_website(entry.get("value"))
                    if site:
                        out["value"] = site
                        kept_sites += 1
                    else:
                        dropped["website_dropped"] += 1
                elif kind in DROPPED_CONTACT_TYPES:
                    dropped[kind] += 1
                    # value omitted on purpose
                else:
                    # Unknown type: drop the value, keep the cite.
                    if entry.get("value"):
                        dropped["other_value"] += 1
                entries_out.append(out)
            groups_out.append({
                "entries": entries_out,
                "entry_count": len(entries_out),
                "purpose": group.get("purpose"),
            })
        families_out.append({
            "filings_reviewed": fam.get("filings_reviewed"),
            "fund_family": fam.get("fund_family"),
            "groups": groups_out,
            "latest_current_485bpos": fam.get("latest_current_485bpos"),
        })
    meta = dict(data.get("meta") or {})
    meta["privacy_note"] = (
        "Individual names, e-mails, phone numbers, and mailing addresses "
        "from filing contacts are not published. Each entry cites the public "
        "SEC source filing; allowlisted institutional websites may be kept. "
        f"Dropped values: {dict(dropped) or 0}."
    )
    meta["note"] = (
        "Contact types as published in fund prospectus filings, without "
        "individual contact details; not legal advice."
    )
    meta["sanitized"] = True
    meta["dropped_values"] = dict(sorted(dropped.items()))
    meta["kept_institutional_websites"] = kept_sites
    meta["entry_count"] = sum(
        len(g.get("entries") or [])
        for fam in families_out
        for g in fam.get("groups") or []
    )
    return {"families": families_out, "meta": meta}, dict(dropped), kept_sites


def export_coverage(conn):
    filings_count = count_or_none(conn, "filings") or 0
    by_year = []
    by_form = []
    filing_date_min = None
    filing_date_max = None
    if table_exists(conn, "filings"):
        by_year = fetchall(conn, """
            SELECT CAST(substr(filing_date, 1, 4) AS INTEGER) AS year,
                   COUNT(*) AS count
            FROM filings
            WHERE filing_date IS NOT NULL AND trim(filing_date) != ''
            GROUP BY 1
            ORDER BY 1
        """)
        by_form = fetchall(conn, """
            SELECT form_type, COUNT(*) AS count
            FROM filings
            GROUP BY 1
            ORDER BY count DESC, form_type
        """)
        row = conn.execute(
            "SELECT MIN(filing_date) AS dmin, MAX(filing_date) AS dmax FROM filings"
        ).fetchone()
        filing_date_min, filing_date_max = row["dmin"], row["dmax"]

    rules = {
        "count": count_or_none(conn, "structured_rules"),
        "by_family_status": [],
        "by_category_status": [],
        "family_coverage_current": [],
    }
    if table_exists(conn, "structured_rules"):
        rules["by_family_status"] = fetchall(conn, """
            SELECT COALESCE(NULLIF(trim(fund_family), ''), '(unset)') AS fund_family,
                   COALESCE(status, '(unset)') AS status,
                   COUNT(*) AS count
            FROM structured_rules
            GROUP BY 1, 2
            ORDER BY 1, 2
        """)
        rules["by_category_status"] = fetchall(conn, """
            SELECT COALESCE(category, '(unset)') AS category,
                   COALESCE(status, '(unset)') AS status,
                   COUNT(*) AS count
            FROM structured_rules
            GROUP BY 1, 2
            ORDER BY 1, 2
        """)
        # Compact form of the proposed v_ui_appendix_i_family_coverage view.
        # Counts only; no condition text, names, or contact details.
        rules["family_coverage_current"] = fetchall(conn, """
            SELECT
              COALESCE(NULLIF(trim(fund_family), ''), '(unset)') AS fund_family,
              SUM(category = 'breakpoint_schedule') AS breakpoint_rows,
              SUM(category = 'roa') AS roa_rows,
              SUM(category = 'loi') AS loi_rows,
              SUM(category = 'sales_charge_waiver') AS waiver_rows,
              SUM(category = 'waiver_limitation') AS limitation_rows,
              SUM(
                category IN ('roa', 'sales_charge_waiver')
                AND instr(lower(coalesce(condition_text, '') || ' ' || coalesce(description, '')),
                          'household') > 0
              ) AS household_rows,
              COUNT(DISTINCT CASE
                WHEN intermediary IS NOT NULL AND trim(intermediary) != ''
                THEN intermediary END) AS named_intermediaries,
              COUNT(*) AS current_rows
            FROM structured_rules
            WHERE status = 'current'
            GROUP BY 1
            ORDER BY 1
        """)

    payload = {
        "filings": {
            "by_form_type": by_form,
            "by_year": by_year,
            "count": filings_count,
            "filing_date_max": filing_date_max,
            "filing_date_min": filing_date_min,
        },
        "funds": {"count": count_or_none(conn, "funds")},
        "share_classes": {"count": count_or_none(conn, "share_classes")},
        "structured_rules": rules,
        "waiver_rules": {"count": count_or_none(conn, "waiver_rules")},
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    out = {
        "meta": {
            "schema": "coverage_slices_v1",
            "title": "MF Compliance library coverage (aggregated, public filings only)",
            "source": (
                "Read-only aggregate export from local mf_compliance.db "
                "(SQLite URI mode=ro). Public SEC filing counts only."
            ),
            "privacy_note": (
                "Aggregates only. No filing body text, no individual names, "
                "e-mails, phone numbers, mailing addresses, or local file paths."
            ),
            "coverage_note": (
                "Counts describe the local library, not a complete historical "
                "universe. Structured rules today cover a subset of fund families. "
                "Automated extracts are unreviewed and are not legal advice."
            ),
            "db_fingerprint_sha256": digest,
            "filing_date_max": filing_date_max,
            "pii_screen": "pending",
        },
        **payload,
    }
    return out


def measure_data_files(out_dir):
    files = []
    raw_total = 0
    gz_total = 0
    for name in DATA_FILES:
        path = Path(out_dir) / name
        if not path.is_file():
            files.append({"name": name, "present": False, "raw_bytes": 0, "gzip_bytes": 0})
            continue
        data = path.read_bytes()
        raw = len(data)
        gz = len(gzip.compress(data, compresslevel=9))
        raw_total += raw
        gz_total += gz
        files.append({
            "name": name,
            "present": True,
            "raw_bytes": raw,
            "gzip_bytes": gz,
        })
    return files, raw_total, gz_total


def screen_data_files(out_dir):
    report = []
    failed = False
    for name in DATA_FILES:
        path = Path(out_dir) / name
        if not path.is_file():
            continue
        hits, _ = pii_screen.scan_json_file(path)
        item = {
            "name": name,
            "hits": len(hits),
            "by_kind": pii_screen.summarize(hits),
            "paths": [h["path"] for h in hits[:20]],
        }
        if hits:
            failed = True
        report.append(item)
    return report, failed


def maybe_run_exporter(exporter, db, out_path, extra_args):
    cmd = [sys.executable, str(exporter), "--db", str(db), "--out", str(out_path)]
    if extra_args:
        cmd.extend(extra_args)
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise RefreshError(f"structured exporter exited {proc.returncode}: {' '.join(cmd)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", help="Path to mf_compliance.db (opened mode=ro)")
    ap.add_argument("--out-dir", default=str(REPO), help="Site root (default: repo root)")
    ap.add_argument("--skip-db", action="store_true",
                    help="Do not export coverage_slices.json (sanitize and screen only)")
    ap.add_argument("--skip-contacts", action="store_true",
                    help="Leave family_contacts.json unchanged")
    ap.add_argument("--structured-exporter", default=None,
                    help="Optional path to export_structured_sample.py (private repo)")
    ap.add_argument("--structured-exporter-arg", action="append", default=None,
                    help="Extra arg for the structured exporter (repeatable)")
    ap.add_argument("--raw-limit", type=int, default=RAW_LIMIT)
    ap.add_argument("--gzip-limit", type=int, default=GZIP_LIMIT)
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_db:
        if not args.db:
            raise RefreshError("--db is required unless --skip-db is set")
        conn = open_readonly(args.db)
        try:
            # Prove the connection cannot write.
            try:
                conn.execute("CREATE TABLE _pilot_refresh_probe (x INTEGER)")
            except sqlite3.OperationalError:
                pass
            else:
                conn.close()
                raise RefreshError("refusing to continue: database connection is not read-only")
            coverage = export_coverage(conn)
        finally:
            conn.close()
        coverage_path = out_dir / "coverage_slices.json"
        coverage["meta"]["pii_screen"] = "pending"
        dump_json(coverage_path, coverage)

    contacts_path = out_dir / "family_contacts.json"
    if not args.skip_contacts and contacts_path.is_file():
        original = json.loads(contacts_path.read_text(encoding="utf-8"))
        sanitized, dropped, kept_sites = sanitize_family_contacts(original)
        dump_json(contacts_path, sanitized)
        print(json.dumps({
            "family_contacts": "sanitized",
            "dropped_values": dropped,
            "kept_institutional_websites": kept_sites,
        }, sort_keys=True))

    if args.structured_exporter:
        if not args.db:
            raise RefreshError("--db is required with --structured-exporter")
        maybe_run_exporter(
            Path(args.structured_exporter),
            args.db,
            out_dir / "structured_rules_sample.json",
            args.structured_exporter_arg or [],
        )

    screen_report, screen_failed = screen_data_files(out_dir)
    files, raw_total, gz_total = measure_data_files(out_dir)

    if not args.skip_db and (out_dir / "coverage_slices.json").is_file():
        coverage = json.loads((out_dir / "coverage_slices.json").read_text(encoding="utf-8"))
        coverage["meta"]["pii_screen"] = "failed" if screen_failed else "passed"
        dump_json(out_dir / "coverage_slices.json", coverage)
        # Re-measure after the pii_screen flag update (byte size may change
        # by a few bytes). Re-screen coverage only — the flag values cannot
        # trip the patterns.
        screen_report, screen_failed = screen_data_files(out_dir)
        files, raw_total, gz_total = measure_data_files(out_dir)

    summary = {
        "out_dir": str(out_dir),
        "files": files,
        "raw_bytes_total": raw_total,
        "gzip_bytes_total": gz_total,
        "raw_limit": args.raw_limit,
        "gzip_limit": args.gzip_limit,
        "pii_screen": screen_report,
        "pii_screen_ok": not screen_failed,
        "size_ok": raw_total <= args.raw_limit and gz_total <= args.gzip_limit,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    errors = []
    if screen_failed:
        errors.append("PII screen failed (see pii_screen paths; matching text is not printed)")
    if raw_total > args.raw_limit or gz_total > args.gzip_limit:
        errors.append(
            f"size cap exceeded: raw {raw_total} / {args.raw_limit}, "
            f"gzip {gz_total} / {args.gzip_limit}"
        )
    if errors:
        raise RefreshError("; ".join(errors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
