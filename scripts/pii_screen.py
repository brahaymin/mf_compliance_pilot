#!/usr/bin/env python3
"""Privacy screen for MF Feedback Pilot static data files.

Patterns are the same ones used by the existing pilot export
(`scripts/export_structured_sample.py` in the private mf_compliance
pipeline): e-mail, phone, street/PO Box, SSN/EIN-like numbers, titled
personal names, and local file paths.

The screen reports hit kind and JSON path only. It never echoes the
matching text, so a failing run cannot leak the contact details it found.

Documentation strings that describe the screen itself (for example a
privacy_note that says "PO Box addresses were excluded") are skipped.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PII = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("phone", re.compile(r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b")),
    ("street_address", re.compile(
        r"\b\d{2,6}\s+(?:[A-Z][a-z]+\s){1,3}"
        r"(?:Street|St\.|Avenue|Ave\.?|Boulevard|Blvd\.?|Road|Rd\.|Drive|Lane|Suite)\b"
    )),
    ("po_box", re.compile(r"\bP\.?\s?O\.?\s+Box\b", re.I)),
    ("ssn_ein", re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{2}-\d{7}\b")),
    ("titled_name", re.compile(r"\b(?:Mr|Mrs|Ms|Dr)\.\s+[A-Z][a-z]+")),
    ("local_path", re.compile(r"(/workspace/|/home/|data/american_funds|\.htm\.gz)")),
]

# Keys whose text describes the screen or the export, not filing content.
SKIP_KEYS = frozenset({
    "privacy_note",
    "coverage_note",
    "selection_note",
    "stale_note",
    "family_logic",
    "source",
})


def iter_strings(obj, path="$", skip_keys=SKIP_KEYS):
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}"
            if key in skip_keys:
                continue
            yield from iter_strings(value, child, skip_keys)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from iter_strings(value, f"{path}[{i}]", skip_keys)
    elif isinstance(obj, str):
        yield path, obj


def scan(obj, skip_keys=SKIP_KEYS):
    """Return a list of {kind, path} hits. Matching text is not included."""
    hits = []
    for path, text in iter_strings(obj, skip_keys=skip_keys):
        for kind, rx in PII:
            if rx.search(text):
                hits.append({"kind": kind, "path": path})
                break
    return hits


def scan_json_file(path, skip_keys=SKIP_KEYS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return scan(data, skip_keys=skip_keys), data


def summarize(hits):
    counts = {}
    for hit in hits:
        counts[hit["kind"]] = counts.get(hit["kind"], 0) + 1
    return counts
