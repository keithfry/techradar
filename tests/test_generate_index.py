"""Tests for .github/scripts/generate-index.sh on a small techradar/ tree."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "generate-index.sh"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    radar = tmp_path / "techradar"
    ai_month = radar / "AI" / "2026-11"
    ai_month.mkdir(parents=True)
    (ai_month / "ai-radar-2026-11-12.html").write_text("<html></html>")
    (ai_month / "ai-radar-2026-11-12.mp3").write_bytes(b"x")
    (radar / "AI" / "podcast.rss").write_text("<rss/>")
    for topic, prefix in (("Research", "research"), ("Robotics", "robotics")):
        month = radar / topic / "2026-11"
        month.mkdir(parents=True)
        (month / f"{prefix}-radar-2026-11-12.html").write_text("<html></html>")
    subprocess.run(["bash", str(SCRIPT), "techradar"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def test_landing_page_links_stylesheet_and_lists_topics(root):
    html = (root / "techradar/index.html").read_text()
    assert '<link rel="stylesheet" href="radar.css">' in html
    assert "<h2>Other</h2>" not in html
    assert html.index('href="./AI"') < html.index('href="./Research"') < html.index('href="./Robotics"')
    assert '<li aria-current="page">Tech Radar</li>' in html


def test_topic_index_bar_and_stylesheet(root):
    html = (root / "techradar/AI/index.html").read_text()
    assert '<link rel="stylesheet" href="../radar.css">' in html
    assert '<a class="site-bar-home" href="https://keithfry.net/">Keith Fry</a>' in html
    assert '<li><a href="../">Tech Radar</a></li>' in html
    assert '<li aria-current="page">AI</li>' in html


def test_month_index_crumbs(root):
    html = (root / "techradar/AI/2026-11/index.html").read_text()
    assert '<link rel="stylesheet" href="../../radar.css">' in html
    assert '<li><a href="../../">Tech Radar</a></li>' in html
    assert '<li><a href="../">AI</a></li>' in html
    assert '<li aria-current="page">November 2026</li>' in html


def test_topic_index_keeps_podcast_and_listen_link(root):
    html = (root / "techradar/AI/index.html").read_text()
    assert 'class="copy-btn"' in html
    assert "<style>" not in html
    assert 'href="./2026-11/ai-radar-2026-11-12.mp3"' in html


def test_viewport_and_doctype(root):
    html = (root / "techradar/AI/index.html").read_text()
    assert html.startswith("<!DOCTYPE html>")
    assert 'name="viewport"' in html


def test_keeps_reload_script(root):
    html = (root / "techradar/AI/index.html").read_text()
    assert 'sessionStorage.setItem(reloadKey, "true")' in html
