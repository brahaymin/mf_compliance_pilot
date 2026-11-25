#!/usr/bin/env python3
"""Shape gate for the published Names Rule pilot JSON (names_policy80.json).

Used by the refresh (which refuses to publish a file that fails) and by the
test suite. Returns human-readable errors; never prints row text.
"""
from __future__ import annotations

REQUIRED = (
    "fund_name",
    "series_id",
    "filing_date",
    "form",
    "accession",
    "sec_filing_url",
    "policy_sentence",
    "status",
)
SEC_PREFIXES = ("https://www.sec.gov/", "https://sec.gov/")


def shape_errors(data, max_errors: int = 20) -> list:
    errors = []

    def add(msg):
        if len(errors) < max_errors:
            errors.append(msg)

    if not isinstance(data, dict):
        return ["top level is not an object"]
    meta = data.get("meta")
    if not isinstance(meta, dict):
        add("meta missing")
        meta = {}
    review = meta.get("review_score")
    if not isinstance(review, dict) or not isinstance(review.get("score_both_correct"), (int, float)):
        add("meta.review_score.score_both_correct missing")
    elif not 0 <= review["score_both_correct"] <= 1:
        add("meta.review_score.score_both_correct out of range")
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        add("rows missing or empty")
        return errors
    if isinstance(meta.get("row_count"), int) and meta["row_count"] != len(rows):
        add(f"meta.row_count {meta['row_count']} != {len(rows)} rows")
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            add(f"row {i} is not an object")
            continue
        missing = [k for k in REQUIRED if k not in row]
        if missing:
            add(f"row {i} missing {missing}")
            continue
        if row["status"] != "pilot":
            add(f"row {i} status is not 'pilot'")
        if not isinstance(row["series_id"], str) or not row["series_id"].strip():
            add(f"row {i} empty series_id")
        url = row["sec_filing_url"]
        if not isinstance(url, str) or not url.startswith(SEC_PREFIXES):
            add(f"row {i} non-SEC URL")
        oc = row.get("other_funds_count")
        if not isinstance(oc, int) or isinstance(oc, bool) or oc < 0:
            add(f"row {i} bad other_funds_count")
        if not isinstance(row.get("note"), str):
            add(f"row {i} note is not a string")
    return errors
