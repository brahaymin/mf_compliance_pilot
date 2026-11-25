from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = "https://mfcompliancepilot.vercel.app/"

def test_docs_stub_has_meta_refresh_and_link():
    for name in ("index.html", "404.html"):
        text = (ROOT / "docs" / name).read_text(encoding="utf-8")
        assert 'http-equiv="refresh"' in text
        assert 'url=https://mfcompliancepilot.vercel.app/' in text
        assert f'href="{DEST}"' in text
        assert "This GitHub Pages copy is retired" in text
        assert "location.replace" in text


def test_root_site_is_not_the_stub():
    """Vercel serves the repo root; the full pilot must stay there."""
    text = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "Names Rule (80% policy)" in text
    assert "December 11, 2026" in text
    assert 'http-equiv="refresh"' not in text
    rules = (ROOT / "rules.html").read_text(encoding="utf-8")
    assert "Mutual Fund Structured Rules" in rules
    assert 'http-equiv="refresh"' not in rules


def test_names_html_redirects_to_front_page():
    text = (ROOT / "names.html").read_text(encoding="utf-8")
    assert 'location.replace("index.html" + window.location.search' in text


def test_front_page_forwards_old_rule_links():
    text = (ROOT / "index.html").read_text(encoding="utf-8")
    assert '"rules.html" + q' in text
