#!/usr/bin/env python3
"""Free uptime check for the live pilot site.

Fetches each public tab and data file; fails (exit 1) on a non-200 status,
a network error, or missing key content. Run hourly by
.github/workflows/uptime.yml (GitHub Actions, free for public repos).
"""
from __future__ import annotations

import argparse
import sys
import urllib.request

BASE = "https://mfcompliancepilot.vercel.app/"
CHECKS = (
    ("", ("Names Rule (80% policy)", "Not legal advice", "December 11, 2026")),
    ("rules.html", ("Mutual Fund Structured Rules", "Sample only")),
    ("priorities.html", ("Free guide", "Not legal advice")),
    ("family-contacts.html", ("Family contacts", "Not legal advice")),
    ("coverage.html", ("Library coverage", "Not legal advice")),
    ("names_policy80.json", ('"review_score"', '"rows"')),
)


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "mf-pilot-uptime/1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
        return resp.status, resp.read().decode("utf-8", "replace")


def run(base=BASE, fetcher=fetch):
    failures = []
    for path, needles in CHECKS:
        url = base + path
        try:
            status, body = fetcher(url)
        except Exception as exc:  # network error, HTTP error, timeout
            failures.append(f"{url}: {type(exc).__name__}: {exc}")
            continue
        if status != 200:
            failures.append(f"{url}: HTTP {status}")
            continue
        missing = [n for n in needles if n not in body]
        if missing:
            failures.append(f"{url}: missing {missing}")
    return failures


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=BASE)
    args = ap.parse_args(argv)
    failures = run(args.base if args.base.endswith("/") else args.base + "/")
    for f in failures:
        print("FAIL " + f)
    print(f"{len(CHECKS) - len(failures)}/{len(CHECKS)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
