"""Headless render tests for every tab JS file on main."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSDOM = ROOT / "tests" / ".jsdom"
SCRIPT = ROOT / "tests" / "render_tabs.js"


def _ensure_jsdom() -> None:
    if (JSDOM / "node_modules" / "jsdom").exists():
        return
    JSDOM.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [
            "npm",
            "install",
            "jsdom@25",
            "--prefix",
            str(JSDOM),
            "--no-audit",
            "--no-fund",
        ],
        cwd=ROOT,
    )


def test_tab_scripts_render_without_throwing():
    _ensure_jsdom()
    env = os.environ.copy()
    env["NODE_PATH"] = str(JSDOM / "node_modules")
    proc = subprocess.run(
        ["node", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
