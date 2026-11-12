#!/usr/bin/env python3
"""One-time conversion of archived digests to the shared radar.css styling.

Replaces each digest's inline <style> block with a link to the stylesheet set
in config's [site] table and adds the site bar after <body>. Article content,
links, tags, podcast players and Open Graph tags are left as they are.
Running it again changes nothing: converted pages are reported as already
restyled.

    uv run scripts/restyle_archive.py --config config/config.toml [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from newsradar.config import Config, load_config
from newsradar.html_generator import digest_page_chrome

_STYLE_RE = re.compile(r"<style>.*?</style>", re.DOTALL)
_MONTH_DIR_RE = re.compile(r"^\d{4}-\d{2}$")
ALREADY_RESTYLED = "already restyled"


class AlreadyRestyled(ValueError):
    """The page has no inline style block and already has the site bar."""


def restyle_digest(html: str, stylesheet_href: str, site_bar: str) -> str:
    """Swap the inline <style> block for a stylesheet link and add the site bar."""
    blocks = _STYLE_RE.findall(html)
    if not blocks and 'class="site-bar"' in html:
        raise AlreadyRestyled(ALREADY_RESTYLED)
    if len(blocks) != 1:
        raise ValueError(f"expected one <style> block, found {len(blocks)}")
    if html.count("<body>\n") != 1:
        raise ValueError("expected one <body> tag followed by a newline")
    link = f'<link rel="stylesheet" href="{stylesheet_href}">'
    html = _STYLE_RE.sub(lambda _: link, html, count=1)
    return html.replace("<body>\n", f"<body>\n{site_bar}\n", 1)


def restyle_tree(
    config: Config, dry_run: bool = False, log=print
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Restyle every <file_prefix>-YYYY-MM-DD.html under each topic's month dirs.

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
                if not match:
                    continue
                date = datetime.strptime(match.group(1), "%Y-%m-%d")
                href, bar = digest_page_chrome(config.site, topic.output_dir, topic.display_name, date)
                if href is None or not bar:
                    raise ValueError("config [site] must set stylesheet and home_url")
                try:
                    new_html = restyle_digest(page.read_text(encoding="utf-8"), href, bar)
                except ValueError as e:
                    skipped.append((page, str(e)))
                    continue
                if not dry_run:
                    page.write_text(new_html, encoding="utf-8")
                changed.append(page)
                log(f"  {'would restyle' if dry_run else 'restyled'}: {page}")
    return changed, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, help="Path to config/config.toml")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change, write nothing")
    args = parser.parse_args(argv)

    changed, skipped = restyle_tree(load_config(args.config), dry_run=args.dry_run, log=lambda *a: None)
    already = [p for p, reason in skipped if reason == ALREADY_RESTYLED]
    failed = [(p, reason) for p, reason in skipped if reason != ALREADY_RESTYLED]
    print(f"changed: {len(changed)}, already restyled: {len(already)}, skipped: {len(failed)}")
    for path, reason in failed:
        print(f"  skipped {path}: {reason}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
