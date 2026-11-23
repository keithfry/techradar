#!/usr/bin/env python3
"""Add card navigation to digest pages generated before news-radar had it.

Each page gets the key help line at the end of its header, and the touch
next/previous buttons and navigation script before </body>. The inserted
markup comes from news-radar's generator, so an updated page matches what
the generator writes today. Pages that already have the help line are
reported as already updated, so running it again changes nothing.

    uv run scripts/add_card_navigation.py --config config/config.toml --since 2026-10-25 [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from newsradar.config import Config, load_config
from newsradar.html_generator import _KB_HELP_HTML, _KB_NAV_JS, _NAV_BUTTONS_HTML

_MONTH_DIR_RE = re.compile(r"^\d{4}-\d{2}$")
_HEADER_OPEN = '<div class="page-header">'
_HEADER_CLOSE = "\n</div>\n"
_BODY_END = "</script>\n</body>"
ALREADY_UPDATED = "already updated"


class AlreadyUpdated(ValueError):
    """The page already has the navigation help line."""


def add_navigation(html: str) -> str:
    """Insert the help line, touch buttons and navigation script."""
    if 'class="kb-help"' in html:
        raise AlreadyUpdated(ALREADY_UPDATED)
    start = html.find(_HEADER_OPEN)
    if start < 0:
        raise ValueError("no page header")
    end = html.find(_HEADER_CLOSE, start)
    if end < 0:
        raise ValueError("page header is not closed")
    if html.count(_BODY_END) != 1:
        raise ValueError("expected one </script> directly before </body>")
    html = html[:end] + _KB_HELP_HTML + html[end:]
    return html.replace(_BODY_END, f"</script>\n{_NAV_BUTTONS_HTML}{_KB_NAV_JS}</body>", 1)


def update_tree(
    config: Config, since: str, dry_run: bool = False, log=print
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Update every <file_prefix>-YYYY-MM-DD.html dated on or after `since`.

    Returns (changed, skipped); skipped holds (path, reason) pairs.
    """
    changed: list[Path] = []
    skipped: list[tuple[Path, str]] = []
    for topic in config.topics.values():
        topic_dir = config.output_root / topic.output_dir
        if not topic_dir.is_dir():
            continue
        page_re = re.compile(rf"^{re.escape(topic.file_prefix)}-(\d{{4}}-\d{{2}}-\d{{2}})\.html$")
        for month_dir in sorted(p for p in topic_dir.iterdir() if p.is_dir() and _MONTH_DIR_RE.match(p.name)):
            for page in sorted(month_dir.iterdir()):
                match = page_re.match(page.name)
                if not match or match.group(1) < since:
                    continue
                try:
                    new_html = add_navigation(page.read_text(encoding="utf-8"))
                except ValueError as e:
                    skipped.append((page, str(e)))
                    continue
                if not dry_run:
                    page.write_text(new_html, encoding="utf-8")
                changed.append(page)
                log(f"  {'would update' if dry_run else 'updated'}: {page}")
    return changed, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, help="Path to config/config.toml")
    parser.add_argument("--since", required=True, help="Oldest page date to update, YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change, write nothing")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since):
        parser.error("--since must be YYYY-MM-DD")

    changed, skipped = update_tree(load_config(args.config), args.since, dry_run=args.dry_run, log=lambda *a: None)
    already = [p for p, reason in skipped if reason == ALREADY_UPDATED]
    failed = [(p, reason) for p, reason in skipped if reason != ALREADY_UPDATED]
    print(f"changed: {len(changed)}, already updated: {len(already)}, skipped: {len(failed)}")
    for path, reason in failed:
        print(f"  skipped {path}: {reason}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
