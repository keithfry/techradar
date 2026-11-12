"""Tests for scripts/restyle_archive.py, the one-time archive conversion."""

from __future__ import annotations

import dataclasses
import re
from datetime import datetime
from pathlib import Path

import pytest

from newsradar.config import load_config
from newsradar.html_generator import generate_html, site_bar_html
from scripts.restyle_archive import AlreadyRestyled, restyle_digest, restyle_tree

from conftest import REPO_ROOT

CONFIG = REPO_ROOT / "config" / "config.toml"
BAR = site_bar_html(
    "https://keithfry.net/", "Keith Fry",
    [("Tech Radar", "../../"), ("AI", "../"), ("November 12, 2026", None)],
)


def _sample(date: datetime = datetime(2026, 11, 12, 8, 0)) -> str:
    return generate_html(
        newsletters=[],
        articles=[{"title": "New model", "link": "https://example.com/a", "source": "Blog",
                   "summary": "Out now.", "tags": ["model"]}],
        papers=[],
        errors=[],
        removed=[{"title": "Ad", "link": "https://example.com/ad", "source": "Spam", "reason": "ad"}],
        date=date,
        topic_label="AI",
        mp3_url="https://example.com/ai-radar-2026-11-12.mp3",
        podcast_rss_url="https://example.com/podcast.rss",
        og_image_url="https://example.com/ai-radar-2026-11-12.og.jpg",
    )


SAMPLE = _sample()
FULL_STYLE_BLOCK = re.search(r"<style>.*?</style>", SAMPLE, re.DOTALL).group(0)


def test_replaces_style_and_adds_bar():
    out = restyle_digest(SAMPLE, "../../radar.css", BAR)
    assert "<style>" not in out
    assert '<link rel="stylesheet" href="../../radar.css">' in out
    assert out.index("<body>") < out.index(BAR) < out.index('<div class="page-header">')


def test_handles_short_old_style_block():
    old = SAMPLE.replace(FULL_STYLE_BLOCK, "<style>\n  body { color: red; }\n</style>")
    out = restyle_digest(old, "../../radar.css", BAR)
    assert "<style>" not in out
    assert "color: red" not in out


def test_leaves_content_untouched():
    out = restyle_digest(SAMPLE, "../../radar.css", BAR)
    for fragment in ('<meta property="og:image"', "<audio controls", 'data-tags="model"', 'id="removed-items"'):
        assert fragment in out
    assert out.replace(BAR + "\n", "").replace('<link rel="stylesheet" href="../../radar.css">', FULL_STYLE_BLOCK) == SAMPLE


def test_second_run_raises_already_restyled():
    once = restyle_digest(SAMPLE, "../../radar.css", BAR)
    with pytest.raises(AlreadyRestyled):
        restyle_digest(once, "../../radar.css", BAR)


def test_two_style_blocks_rejected():
    with pytest.raises(ValueError):
        restyle_digest(SAMPLE.replace("</head>", "<style></style></head>"), "../../radar.css", BAR)


def test_missing_body_rejected():
    with pytest.raises(ValueError):
        restyle_digest(SAMPLE.replace("<body>", "<body class=x>"), "../../radar.css", BAR)


def _cfg(tmp_path: Path):
    return dataclasses.replace(load_config(CONFIG), output_root=tmp_path)


def _write(tmp_path: Path, rel: str, text: str) -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_restyle_tree_counts_and_dates(tmp_path):
    a = _write(tmp_path, "AI/2026-11/ai-radar-2026-11-12.html", SAMPLE)
    b = _write(tmp_path, "AI/2026-06/ai-radar-2026-06-14.html", _sample(datetime(2026, 6, 14, 8, 0)))
    done = _write(tmp_path, "Robotics/2026-11/robotics-radar-2026-11-12.html",
                  restyle_digest(SAMPLE, "../../radar.css", BAR))
    _write(tmp_path, "AI/2026-11/index.html", "<html><body>index</body></html>")

    changed, skipped = restyle_tree(_cfg(tmp_path), log=lambda *a: None)

    assert sorted(changed) == sorted([a, b])
    assert skipped == [(done, "already restyled")]
    assert '<li aria-current="page">November 12, 2026</li>' in a.read_text()
    assert '<li aria-current="page">June 14, 2026</li>' in b.read_text()
    assert '<li><a href="../">AI</a></li>' in a.read_text()


def test_dry_run_writes_nothing(tmp_path):
    page = _write(tmp_path, "AI/2026-11/ai-radar-2026-11-12.html", SAMPLE)
    changed, _ = restyle_tree(_cfg(tmp_path), dry_run=True, log=lambda *a: None)
    assert changed == [page]
    assert page.read_text() == SAMPLE


def test_repo_config_opts_in():
    site = load_config(CONFIG).site
    assert (site.stylesheet, site.home_url, site.home_label, site.section_label) == (
        "radar.css", "https://keithfry.net/", "Keith Fry", "Tech Radar")
