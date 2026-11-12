"""Checks on techradar/radar.css: WCAG AA contrast and coverage of generator classes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from newsradar.html_generator import _CSS

CSS_PATH = Path(__file__).resolve().parents[1] / "techradar" / "radar.css"

TAGS = ("policy", "model", "agents", "safety", "robotics", "voice", "health", "research", "ethics")
PAIRS = [
    ("--kf-text", "--kf-bg"), ("--kf-text", "--kf-surface"), ("--kf-muted", "--kf-bg"),
    ("--kf-muted", "--kf-surface"), ("--kf-muted", "--kf-surface-2"), ("--kf-muted", "--kf-footer"),
    ("--kf-heading", "--kf-surface"), ("--kf-link", "--kf-bg"), ("--kf-link", "--kf-surface"),
    ("--kf-link", "--kf-surface-2"), ("--kf-link-hover", "--kf-surface"), ("--kf-on-accent", "--kf-accent"),
    ("--kf-danger", "--kf-surface"), ("--kf-arxiv", "--kf-surface"), ("--kf-robotics", "--kf-surface"),
] + [(f"--tag-{k}-fg", f"--tag-{k}-bg") for k in TAGS]


def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def _tokens() -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", _css()))


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("fg,bg", PAIRS)
def test_pair_meets_wcag_aa(fg, bg):
    tokens = _tokens()
    ratio = _contrast(tokens[fg], tokens[bg])
    assert ratio >= 4.5, f"{fg} on {bg} is {ratio:.2f}:1"


def test_site_colors_match_keithfry_net():
    tokens = _tokens()
    assert tokens["--kf-bg"] == "#0f172a"
    assert tokens["--kf-text"] == "#cbd5e1"
    assert tokens["--kf-heading"] == "#f1f5f9"
    assert tokens["--kf-link"] == "#748ffc"
    assert tokens["--kf-accent"] == "#4361ee"


def test_no_root_relative_or_wordpress_urls():
    css = _css()
    assert "url(/" not in css
    assert "astra/assets" not in css
    assert "elementor" not in css


def test_styles_every_generator_class():
    generator_classes = set(re.findall(r"\.([a-zA-Z][\w-]*)", _CSS))
    css = _css()
    missing = sorted(c for c in generator_classes if not re.search(rf"\.{re.escape(c)}\b", css))
    assert missing == []


def test_styles_site_bar_and_index_classes():
    css = _css()
    for cls in ("site-bar", "site-bar-home", "site-bar-crumbs", "index-title",
                "digest-list", "topic-list", "podcast-bar", "copy-btn"):
        assert f".{cls}" in css, cls
