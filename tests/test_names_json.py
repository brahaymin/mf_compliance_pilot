"""Shape checks for the published Names Rule pilot JSON."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = {
    "fund_name",
    "series_id",
    "filing_date",
    "form",
    "accession",
    "sec_filing_url",
    "policy_sentence",
    "status",
}


def test_names_policy80_rows_are_pilot_with_required_fields():
    data = json.loads((ROOT / "names_policy80.json").read_text(encoding="utf-8"))
    rows = data["rows"]
    assert isinstance(rows, list)
    assert rows
    for i, row in enumerate(rows):
        missing = REQUIRED - set(row)
        assert not missing, f"row {i} missing {sorted(missing)}"
        assert row["status"] == "pilot", f"row {i} status={row['status']!r}"
        series_id = row["series_id"]
        assert isinstance(series_id, str) and series_id.strip(), f"row {i} empty series_id"
        url = row["sec_filing_url"]
        assert isinstance(url, str)
        assert url.startswith("https://www.sec.gov/") or url.startswith(
            "https://sec.gov/"
        ), f"row {i} non-SEC URL"
