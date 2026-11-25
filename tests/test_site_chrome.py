"""Every tab shares the same header, banner, accuracy status and footer."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import site_chrome  # noqa: E402

PAGES = [p for p, _, _ in site_chrome.PAGES]


def _block(text, name):
    m = re.search(rf"<!-- site-chrome:{name} -->(.*?)<!-- /site-chrome:{name} -->", text, re.S)
    assert m, name
    return m.group(1)


def test_pages_are_up_to_date():
    assert site_chrome.apply(ROOT, check=True) == []


def test_all_tabs_share_banner_nav_footer():
    navs = set()
    for page in PAGES:
        text = (ROOT / page).read_text(encoding="utf-8")
        header = _block(text, "header")
        assert "Not legal advice" in header
        assert "Public SEC EDGAR data only" in header
        assert "2020 onward only" in header
        assert "automatically" in header
        assert f'href="{page}" aria-current="page"' in header
        navs.add(header.replace(' aria-current="page"', ""))
        assert "site.css" in text and "pilot.css?v=20261125-launch" in text
        assert _block(text, "footer").strip()
    assert len(navs) == 1


def test_accuracy_status_is_honest():
    meta = json.loads((ROOT / "names_policy80.json").read_text(encoding="utf-8"))["meta"]
    score = meta["review_score"]["score_both_correct"]
    for page in PAGES:
        acc = _block((ROOT / page).read_text(encoding="utf-8"), "accuracy")
        if page == "index.html":
            assert 'data-accuracy="graded"' in acc
            assert f"{score:.2f}" in acc
            assert "Quality gate" in acc and "Known limitation" in acc
        else:
            assert 'data-accuracy="unreviewed"' in acc


def test_no_bare_098_on_site():
    for path in list(ROOT.glob("*.html")) + list(ROOT.glob("*.js")):
        assert "0.98" not in path.read_text(encoding="utf-8"), path.name


def test_rules_labeled_sample_and_priorities_free_guide():
    assert "Sample only" in (ROOT / "rules.html").read_text(encoding="utf-8")
    assert "Free guide" in (ROOT / "priorities.html").read_text(encoding="utf-8")


def test_check_mode_detects_stale_page(tmp_path):
    for page in PAGES + ["names_policy80.json"]:
        (tmp_path / page).write_bytes((ROOT / page).read_bytes())
    data = json.loads((tmp_path / "names_policy80.json").read_text(encoding="utf-8"))
    data["meta"]["review_score"]["score_both_correct"] = 0.5
    (tmp_path / "names_policy80.json").write_text(json.dumps(data), encoding="utf-8")
    assert site_chrome.apply(tmp_path, check=True) == ["index.html"]
    site_chrome.apply(tmp_path)
    assert "0.50" in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_no_contact_address_or_form_anywhere():
    """CEO 2026-11-25: no contact address, mailto, or contact form."""
    files = list(ROOT.glob("*.html")) + list(ROOT.glob("*.js")) + list((ROOT / "docs" / "drafts").glob("*.md"))
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        assert "mailto:" not in text, path.name
        # Only search boxes; no contact or request form.
        for chunk in text.split("<form")[1:]:
            assert 'role="search"' in chunk.split(">", 1)[0], path.name
    for path in (ROOT / "docs" / "drafts").glob("*.md"):
        assert "@" not in path.read_text(encoding="utf-8"), path.name
