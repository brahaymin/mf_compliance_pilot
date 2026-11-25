"""Shape checks for the published Names Rule pilot JSON."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import names_gate  # noqa: E402


def test_published_names_json_passes_shape_gate():
    data = json.loads((ROOT / "names_policy80.json").read_text(encoding="utf-8"))
    assert names_gate.shape_errors(data) == []


def _good():
    return {
        "meta": {"row_count": 1, "review_score": {"score_both_correct": 0.9, "n": 20}},
        "rows": [{
            "fund_name": "Example Equity Fund", "series_id": "S000000001",
            "filing_date": "2024-01-02", "form": "485BPOS",
            "accession": "0000000000-24-000001",
            "sec_filing_url": "https://www.sec.gov/Archives/edgar/data/1/a.htm",
            "policy_sentence": "The Fund invests at least 80% of its net assets in equity securities.",
            "status": "pilot", "other_funds_count": 0, "note": "",
        }],
    }


def test_shape_gate_flags_bad_rows():
    assert names_gate.shape_errors(_good()) == []
    bad = _good()
    bad["rows"][0]["sec_filing_url"] = "https://example.com/x"
    bad["rows"][0]["status"] = "final"
    del bad["meta"]["review_score"]
    errs = names_gate.shape_errors(bad)
    assert any("non-SEC" in e for e in errs)
    assert any("status" in e for e in errs)
    assert any("review_score" in e for e in errs)
    assert names_gate.shape_errors({"meta": {}, "rows": []})
