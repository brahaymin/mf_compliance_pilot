from pathlib import Path
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import pii_screen  # noqa: E402


def test_screen_finds_each_kind_without_echoing_text():
    payload = {
        "email": "someone@example.com",
        "phone": "212-555-0100",
        "street": "100 Main Street",
        "po": "P.O. Box 123",
        "ssn": "123-45-6789",
        "name": "Mr. Smith",
        "path": "/workspace/secret/file",
    }
    hits = pii_screen.scan(payload)
    kinds = {h["kind"] for h in hits}
    assert kinds == {
        "email", "phone", "street_address", "po_box", "ssn_ein", "titled_name", "local_path",
    }
    blob = json.dumps(hits)
    assert "someone@example.com" not in blob
    assert "212-555-0100" not in blob
    assert "Mr. Smith" not in blob


def test_privacy_note_mentioning_po_box_is_skipped():
    payload = {
        "meta": {
            "privacy_note": "Entries with street/PO Box addresses were excluded."
        },
        "rules": [{"description": "No sales load."}],
    }
    assert pii_screen.scan(payload) == []


def test_scan_json_file(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text(json.dumps({"rules": [{"description": "Call 415-555-0100 now"}]}), encoding="utf-8")
    hits, data = pii_screen.scan_json_file(path)
    assert data["rules"][0]["description"].startswith("Call")
    assert hits == [{"kind": "phone", "path": "$.rules[0].description"}]
