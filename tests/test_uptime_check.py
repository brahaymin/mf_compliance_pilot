import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import uptime_check  # noqa: E402

LOCAL = {"": "index.html"}


def _local_fetch(url):
    name = url.replace(uptime_check.BASE, "")
    return 200, (ROOT / LOCAL.get(name, name)).read_text(encoding="utf-8")


def test_repo_pages_satisfy_uptime_content_checks():
    assert uptime_check.run(fetcher=_local_fetch) == []


def test_non_200_and_missing_content_fail():
    def bad(url):
        if url.endswith("coverage.html"):
            return 503, ""
        if url.endswith("rules.html"):
            raise OSError("down")
        return 200, "nothing here"
    failures = uptime_check.run(fetcher=bad)
    assert len(failures) == len(uptime_check.CHECKS)
    assert any("HTTP 503" in f for f in failures)
    assert any("OSError" in f for f in failures)
