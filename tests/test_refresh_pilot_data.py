from pathlib import Path
import json
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from helpers import make_db  # noqa: E402
import refresh_pilot_data as refresh  # noqa: E402
import pii_screen  # noqa: E402

# Synthetic filings only. No real personal names, e-mails, or phones.
FILINGS = [
    (1, "485BPOS", "0000000000-20-000001", "2020-06-15", "https://www.sec.gov/Archives/edgar/data/1/a.htm"),
    (2, "497", "0000000000-21-000002", "2021-03-01", "https://www.sec.gov/Archives/edgar/data/1/b.htm"),
    (3, "497K", "0000000000-21-000003", "2021-03-02", "https://www.sec.gov/Archives/edgar/data/1/c.htm"),
    (4, "485BPOS", "0000000000-22-000004", "2022-11-01", "https://www.sec.gov/Archives/edgar/data/1/d.htm"),
]
FUNDS = [(1, "0000000001", "S000000001", "Example Trust Equity Fund", None)]
CLASSES = [(1, 1, "EXAAA", "Class A", "C000000001")]
RULES = [
    (1, "sales_charge_waiver", "waiver for retirement plans", "household accounts", None,
     "EXAAA", "Example Trust", "0000000000-22-000004", "485BPOS", "2022-11-01", "Example Broker LLC", "current"),
    (2, "roa", "rights of accumulation", None, None,
     "EXAAA", "Example Trust", "0000000000-22-000004", "485BPOS", "2022-11-01", None, "current"),
    (3, "loi", "letter of intent", None, None,
     "EXAAA", "Example Trust", "0000000000-20-000001", "485BPOS", "2020-06-15", None, "historical"),
    (4, "breakpoint_schedule", "schedule", None, None,
     "EXAAA", "Example Trust", "0000000000-22-000004", "485BPOS", "2022-11-01", None, "current"),
]


def write_contacts(path, *, phone="212-555-0199", site="https://www.fidelity.com/login"):
    data = {
        "meta": {
            "title": "test contacts",
            "note": "synthetic",
            "families": ["Example Trust"],
            "entry_count": 3,
            "privacy_note": "test",
        },
        "families": [{
            "fund_family": "Example Trust",
            "latest_current_485bpos": "2022-11-01",
            "filings_reviewed": 2,
            "groups": [{
                "purpose": "Shareholder services",
                "entries": [
                    {
                        "type": "phone",
                        "label": "Service line",
                        "value": phone,
                        "accession": "0000000000-22-000004",
                        "filing_date": "2022-11-01",
                        "form_type": "485BPOS",
                        "edgar_url": "https://www.sec.gov/Archives/edgar/data/1/d.htm",
                    },
                    {
                        "type": "address",
                        "label": "Mail",
                        "value": "100 Main Street, Boston, MA 02110",
                        "accession": "0000000000-22-000004",
                        "filing_date": "2022-11-01",
                        "form_type": "485BPOS",
                        "edgar_url": "https://www.sec.gov/Archives/edgar/data/1/d.htm",
                    },
                    {
                        "type": "website",
                        "label": "Website",
                        "value": site,
                        "accession": "0000000000-22-000004",
                        "filing_date": "2022-11-01",
                        "form_type": "485BPOS",
                        "edgar_url": "https://www.sec.gov/Archives/edgar/data/1/d.htm",
                    },
                ],
            }],
        }],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_open_readonly_rejects_writes(tmp_path):
    db = make_db(tmp_path / "t.db", filings=FILINGS)
    conn = refresh.open_readonly(db)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("CREATE TABLE should_not_exist (x INTEGER)")
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO filings(filing_id) VALUES (99)")
    conn.close()


def test_coverage_export_is_deterministic(tmp_path):
    db = make_db(tmp_path / "t.db", filings=FILINGS, structured_rules=RULES, funds=FUNDS, share_classes=CLASSES)
    conn = refresh.open_readonly(db)
    a = refresh.export_coverage(conn)
    b = refresh.export_coverage(conn)
    conn.close()
    assert a == b
    assert a["filings"]["count"] == 4
    assert a["filings"]["by_year"] == [
        {"year": 2020, "count": 1},
        {"year": 2021, "count": 2},
        {"year": 2022, "count": 1},
    ]
    forms = {row["form_type"]: row["count"] for row in a["filings"]["by_form_type"]}
    assert forms == {"485BPOS": 2, "497": 1, "497K": 1}
    families = {row["fund_family"] for row in a["structured_rules"]["by_family_status"]}
    assert families == {"Example Trust"}
    coverage = a["structured_rules"]["family_coverage_current"]
    assert len(coverage) == 1
    assert coverage[0]["waiver_rows"] == 1
    assert coverage[0]["household_rows"] == 1
    assert coverage[0]["named_intermediaries"] == 1
    # Aggregates must not carry filing body text or contact values.
    blob = json.dumps(a)
    assert "212-555" not in blob
    assert "Main Street" not in blob
    assert "household accounts" not in blob


def test_sanitize_drops_phone_and_address_keeps_allowlisted_site():
    data = json.loads(json.dumps({
        "meta": {"title": "t", "entry_count": 3},
        "families": [{
            "fund_family": "Example Trust",
            "latest_current_485bpos": "2022-11-01",
            "filings_reviewed": 2,
            "groups": [{
                "purpose": "Shareholder services",
                "entries": [
                    {"type": "phone", "label": "Service line", "value": "212-555-0199",
                     "accession": "0000000000-22-000004", "filing_date": "2022-11-01",
                     "form_type": "485BPOS", "edgar_url": "https://www.sec.gov/Archives/edgar/data/1/d.htm"},
                    {"type": "address", "label": "Mail", "value": "100 Main Street",
                     "accession": "0000000000-22-000004", "filing_date": "2022-11-01",
                     "form_type": "485BPOS", "edgar_url": "https://www.sec.gov/Archives/edgar/data/1/d.htm"},
                    {"type": "website", "label": "Website", "value": "https://www.fidelity.com/login?user=1",
                     "accession": "0000000000-22-000004", "filing_date": "2022-11-01",
                     "form_type": "485BPOS", "edgar_url": "https://www.sec.gov/Archives/edgar/data/1/d.htm"},
                    {"type": "website", "label": "Other", "value": "https://evil.example/phish",
                     "accession": "0000000000-22-000004", "filing_date": "2022-11-01",
                     "form_type": "485BPOS", "edgar_url": "https://www.sec.gov/Archives/edgar/data/1/d.htm"},
                ],
            }],
        }],
    }))
    out, dropped, kept = refresh.sanitize_family_contacts(data)
    values = [e.get("value") for e in out["families"][0]["groups"][0]["entries"]]
    assert "212-555-0199" not in values
    assert "100 Main Street" not in values
    assert "https://www.fidelity.com/" in values
    assert "https://evil.example/phish" not in values
    assert dropped["phone"] == 1
    assert dropped["address"] == 1
    assert dropped["website_dropped"] == 1
    assert kept == 1
    assert pii_screen.scan(out) == []


def test_refresh_twice_is_idempotent(tmp_path):
    db = make_db(tmp_path / "t.db", filings=FILINGS, structured_rules=RULES, funds=FUNDS, share_classes=CLASSES)
    out = tmp_path / "site"
    out.mkdir()
    write_contacts(out / "family_contacts.json")
    argv = ["--db", str(db), "--out-dir", str(out)]
    assert refresh.main(argv) == 0
    first = (out / "coverage_slices.json").read_bytes()
    first_contacts = (out / "family_contacts.json").read_bytes()
    assert refresh.main(argv) == 0
    assert (out / "coverage_slices.json").read_bytes() == first
    assert (out / "family_contacts.json").read_bytes() == first_contacts
    # Connection used mode=ro: the synthetic DB file bytes may change if
    # SQLite checkpoints, but our script must not create new tables.
    conn = sqlite3.connect(db)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "_pilot_refresh_probe" not in names
    payload = json.loads(first)
    assert payload["meta"]["pii_screen"] == "passed"
    assert payload["meta"]["schema"] == "coverage_slices_v1"
    assert "generated_at" not in payload["meta"]


def test_pii_hit_fails_the_run(tmp_path):
    db = make_db(tmp_path / "t.db", filings=FILINGS)
    out = tmp_path / "site"
    out.mkdir()
    # A data file the size budget includes, with a phone that is not in a skip key.
    (out / "issue_map.json").write_text(json.dumps({"items": [{"blurb": "Call 212-555-0100"}]}), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        refresh.main(["--db", str(db), "--out-dir", str(out), "--skip-contacts"])
    assert "PII screen failed" in str(exc.value)


def test_size_cap_fails_the_run(tmp_path):
    db = make_db(tmp_path / "t.db", filings=FILINGS)
    out = tmp_path / "site"
    out.mkdir()
    (out / "sample_rules.json").write_text(json.dumps({"pad": "a" * 200}), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        refresh.main(["--db", str(db), "--out-dir", str(out), "--skip-contacts",
                      "--raw-limit", "50", "--gzip-limit", "100000"])
    assert "size cap exceeded" in str(exc.value)
