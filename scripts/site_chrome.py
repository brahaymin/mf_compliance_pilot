#!/usr/bin/env python3
"""Shared header, banner, accuracy status, and footer for every pilot tab.

Each page carries generated blocks between ``<!-- site-chrome:NAME -->`` and
``<!-- /site-chrome:NAME -->`` markers. Run this script after editing the
chrome or refreshing ``names_policy80.json``; ``--check`` exits non-zero
when any page is stale (the test suite and the refresh both use it).

The Names accuracy line is rendered from ``meta.review_score`` in
``names_policy80.json`` so the published score cannot drift from the data.
All other tabs say "unreviewed" until they are graded.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (file, nav label, accuracy kind)
PAGES = (
    ("index.html", "Names rule", "names"),
    ("rules.html", "Rules (sample)", "unreviewed"),
    ("priorities.html", "Free guide", "unreviewed"),
    ("family-contacts.html", "Family contacts", "unreviewed"),
    ("coverage.html", "Coverage", "unreviewed"),
    ("fees.html", "Fee changes", "fees"),
    ("etf.html", "MF to ETF", "etf"),
)

BANNER = (
    "Not legal advice. Public SEC EDGAR data only. "
    "v1 covers filings from 2020 onward only. "
    "Built automatically from filings; check the linked SEC document."
)

FOOTER = (
    "MF Feedback Pilot. Free and automated. Not legal advice. "
    "Public SEC EDGAR data only; v1 covers 2020 onward."
)

FEES = (
    "Accuracy: supervised pilot. Every change shown was checked by hand against the fee "
    "tables of both filings; unconfirmed rows are not published. Not graded on a random "
    "sample, and not complete: filings without a single Series ID are skipped."
)

ETF = (
    "Accuracy: lineage: unreviewed; fees: 295 of 297 active share classes published on CEO go "
    "2026-11-26 11:36 AM CT (Total and Net for ETF and sister classes; waiver shown when above 0). "
    "Two active ETF classes that are not yet effective, and four closed-series older classes, have "
    "no usable fee (reason shown). Inactive classes are hidden. Supervised pilot. Read the full "
    "filing; check each item against the linked SEC document."
)

UNREVIEWED = (
    "Accuracy: unreviewed. This tab has not been graded yet; "
    "check each item against the linked SEC filing."
)


class ChromeError(RuntimeError):
    pass


def names_accuracy(names_json: Path) -> str:
    data = json.loads(names_json.read_text(encoding="utf-8"))
    review = (data.get("meta") or {}).get("review_score")
    if not isinstance(review, dict) or not isinstance(review.get("score_both_correct"), (int, float)):
        raise ChromeError("names_policy80.json meta.review_score.score_both_correct is missing")
    parts = [
        "Accuracy: graded {:.2f} (fund name and policy sentence both correct) on a random sample of {} rows".format(
            review["score_both_correct"], review.get("n", "?")),
    ]
    if isinstance(review.get("policy_sentence_score"), (int, float)):
        parts[0] += "; policy sentence alone {:.2f}".format(review["policy_sentence_score"])
    parts[0] += "."
    if review.get("gate"):
        parts.append("Quality gate ({}): {}.".format(review["gate"], review.get("gate_result", "not recorded")))
    if review.get("known_limitation"):
        parts.append("Known limitation: {}".format(review["known_limitation"]))
    return " ".join(parts)


def blocks_for(page: str, kind: str, names_text: str) -> dict:
    links = []
    for name, label, _ in PAGES:
        cur = ' aria-current="page"' if name == page else ""
        links.append(f'    <a href="{name}"{cur}>{html.escape(label)}</a>')
    header = (
        '<header class="site-header">\n'
        '  <nav class="site-nav" aria-label="Pilot pages">\n'
        '    <a class="site-brand" href="index.html">MF Feedback Pilot</a>\n'
        + "\n".join(links) + "\n"
        "  </nav>\n"
        f'  <p class="site-banner" role="note">{html.escape(BANNER)}</p>\n'
        "</header>"
    )
    text = {"names": names_text, "fees": FEES, "etf": ETF}.get(kind, UNREVIEWED)
    status = {"names": "graded", "fees": "supervised", "etf": "supervised"}.get(kind, "unreviewed")
    accuracy = f'<p class="accuracy-status" data-accuracy="{status}">{html.escape(text)}</p>'
    footer = (f'<footer class="site-footer"><p>{html.escape(FOOTER)}</p></footer>\n'
              '<script src="site.js?v=20261125-links" defer></script>')
    return {"header": header, "accuracy": accuracy, "footer": footer}


def wrap(name: str, body: str) -> str:
    return f"<!-- site-chrome:{name} -->\n{body}\n<!-- /site-chrome:{name} -->"


def render(text: str, blocks: dict) -> str:
    for name, body in blocks.items():
        pat = re.compile(rf"<!-- site-chrome:{name} -->.*?<!-- /site-chrome:{name} -->", re.S)
        if pat.search(text):
            text = pat.sub(lambda _m: wrap(name, body), text, count=1)
            continue
        # First run: place the block.
        if name == "header":
            nav = re.compile(r'<nav class="site-nav".*?</nav>', re.S)
            if not nav.search(text):
                raise ChromeError("no site-nav to replace")
            text = nav.sub(lambda _m: wrap(name, body), text, count=1)
        elif name == "accuracy":
            idx = text.index("</header>", text.index('<main class="wrap">')) + len("</header>")
            text = text[:idx] + "\n" + wrap(name, body) + text[idx:]
        elif name == "footer":
            idx = text.index("</main>") + len("</main>")
            text = text[:idx] + "\n" + wrap(name, body) + text[idx:]
    if 'href="site.css' not in text:
        text = text.replace("</head>", '  <link rel="stylesheet" href="site.css?v=20261125-fees">\n</head>', 1)
    return text


def apply(root: Path = REPO, check: bool = False) -> list:
    names_text = names_accuracy(root / "names_policy80.json")
    stale = []
    for page, _label, kind in PAGES:
        path = root / page
        old = path.read_text(encoding="utf-8")
        new = render(old, blocks_for(page, kind, names_text))
        if new != old:
            stale.append(page)
            if not check:
                path.write_text(new, encoding="utf-8")
    return stale


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--check", action="store_true", help="Fail if any page is stale; write nothing")
    args = ap.parse_args(argv)
    stale = apply(Path(args.root), check=args.check)
    if args.check and stale:
        print("stale site chrome: " + ", ".join(stale) + " (run scripts/site_chrome.py)", file=sys.stderr)
        return 1
    print(json.dumps({"updated" if not args.check else "checked": stale or "none"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
