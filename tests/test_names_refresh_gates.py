"""The weekly Names update is folded into the refresh behind two gates.

Synthetic data only: the PII example uses a 555 test number.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import refresh_pilot_data as refresh  # noqa: E402
from test_names_json import _good  # noqa: E402

ARGS = ["--skip-db", "--skip-contacts"]


def _site(tmp_path):
    out = tmp_path / "site"
    out.mkdir()
    published = _good()
    published["rows"][0]["fund_name"] = "Published Fund"
    (out / "names_policy80.json").write_text(json.dumps(published), encoding="utf-8")
    return out


def _candidate(tmp_path, data):
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _published_name(out):
    return json.loads((out / "names_policy80.json").read_text(encoding="utf-8"))["rows"][0]["fund_name"]


def test_good_candidate_is_published(tmp_path):
    out = _site(tmp_path)
    cand = _candidate(tmp_path, _good())
    assert refresh.main(ARGS + ["--out-dir", str(out), "--names-json", str(cand)]) == 0
    assert _published_name(out) == "Example Equity Fund"


def test_pii_in_candidate_blocks_publish(tmp_path):
    out = _site(tmp_path)
    bad = _good()
    bad["rows"][0]["note"] = "Questions: call 212-555-0100"
    with pytest.raises(SystemExit) as exc:
        refresh.main(ARGS + ["--out-dir", str(out), "--names-json", str(_candidate(tmp_path, bad))])
    assert "names PII screen failed; not published" in str(exc.value)
    assert "212-555" not in str(exc.value)
    assert _published_name(out) == "Published Fund"


def test_bad_shape_blocks_publish(tmp_path):
    out = _site(tmp_path)
    bad = _good()
    del bad["rows"][0]["series_id"]
    with pytest.raises(SystemExit) as exc:
        refresh.main(ARGS + ["--out-dir", str(out), "--names-json", str(_candidate(tmp_path, bad))])
    assert "names shape gate failed; not published" in str(exc.value)
    assert _published_name(out) == "Published Fund"


def test_published_names_file_is_screened_and_shape_checked(tmp_path):
    out = _site(tmp_path)
    data = json.loads((out / "names_policy80.json").read_text(encoding="utf-8"))
    data["rows"][0]["status"] = "final"
    (out / "names_policy80.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        refresh.main(ARGS + ["--out-dir", str(out)])
    assert "names shape gate failed" in str(exc.value)
    assert "names_policy80.json" in refresh.DATA_FILES
