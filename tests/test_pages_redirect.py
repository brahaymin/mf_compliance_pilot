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
    assert "Mutual Fund Structured Rules" in text
    assert 'http-equiv="refresh"' not in text
