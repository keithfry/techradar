"""Tests for scripts/add_card_navigation.py, the card navigation backfill."""

from __future__ import annotations

from datetime import datetime

import pytest

from newsradar.html_generator import _KB_HELP_HTML, _KB_NAV_JS, _NAV_BUTTONS_HTML, generate_html
from scripts.add_card_navigation import AlreadyUpdated, add_navigation


def _current_page(**kwargs) -> str:
    return generate_html(
        newsletters=[],
        articles=[{"title": "New model", "link": "https://example.com/a", "source": "Blog",
                   "summary": "Out now.", "tags": ["model"]}],
        papers=[],
        errors=[],
        date=datetime(2026, 11, 12, 8, 0),
        **kwargs,
    )


def _old_page(**kwargs) -> str:
    """The same page as the generator wrote it before card navigation."""
    html = _current_page(**kwargs)
    assert html.count(_KB_HELP_HTML) == 1 and html.count(_NAV_BUTTONS_HTML + _KB_NAV_JS) == 1
    return html.replace(_KB_HELP_HTML, "").replace(_NAV_BUTTONS_HTML + _KB_NAV_JS, "")


@pytest.mark.parametrize("kwargs", [
    {},
    {"mp3_url": "https://example.com/a.mp3", "podcast_rss_url": "https://example.com/p.rss"},
])
def test_updated_page_matches_generator_output(kwargs):
    assert add_navigation(_old_page(**kwargs)) == _current_page(**kwargs)


def test_second_run_reports_already_updated():
    with pytest.raises(AlreadyUpdated):
        add_navigation(_current_page())


def test_rejects_page_without_header():
    html = _old_page().replace('<div class="page-header">', '<div class="other">')
    with pytest.raises(ValueError, match="no page header"):
        add_navigation(html)
