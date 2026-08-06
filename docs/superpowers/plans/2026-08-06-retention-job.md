# Retention Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manually-triggered retention job that purges audio artifacts from radar episodes older than 90 days and whole episodes older than 150 days, regenerates the RSS/index files, and commits+pushes (unless `--dry-run`).

**Architecture:** Pure purge logic lives in the `newsradar` package (`news-radar` repo) as two functions operating on `Path`s with an injected `now`, fully unit-testable. A thin orchestrator script in the `techradar` repo (mirroring the existing `run.py`/`run-agent.sh` pair) wires config, calls the purge functions per topic, regenerates `podcast.rss` and `index.html`, and handles git commit/push.

**Tech Stack:** Python 3.13, `unittest` (matching existing `news-radar` test style), bash, existing `newsradar` config/topics/podcast_rss modules, existing `.github/scripts/generate-index.sh`.

## Global Constraints

- Age is computed from the date encoded in the filename stem (e.g. `ai-radar-2026-05-01`), never from file mtime.
- Audio-artifact purge threshold: 90 days. Full-episode purge threshold: 150 days.
- Audio artifacts = `.mp3`, `.chapters.json`, `.transcript.json`, `.jpg`, `.og.jpg`.
- When audio artifacts are purged but the episode's `.html` survives, strip the inline `<div class="podcast-player">...</div>` block and the `og:image`/`twitter:image` meta lines from that HTML.
- `--dry-run` still performs all file deletions/edits on disk (so `git status`/`git diff` show the real effect) — it only skips the final `git commit`/`git push`.
- Missing files during a delete are not errors (`missing_ok=True` / idempotent).
- Follow existing code style: type-hinted Python, `unittest.TestCase` + `tempfile.TemporaryDirectory` for `news-radar` tests (see `tests/test_podcast_rss.py`).

---

### Task 1: Shared filename-date helper

**Files:**
- Create: `news-radar/src/newsradar/filename_dates.py`
- Modify: `news-radar/src/newsradar/podcast_rss.py:35-45` (replace `_date_from_stem`'s body to delegate to the new helper)
- Test: `news-radar/tests/test_filename_dates.py`

**Interfaces:**
- Produces: `parse_date_from_stem(stem: str, prefix: str) -> date | None` — parses `YYYY-MM-DD` out of a stem like `"ai-radar-2026-05-21"` given `prefix="ai-radar"`. Returns `None` if unparseable. Used by Task 2's `retention.py` and by `podcast_rss.py`.

- [ ] **Step 1: Write the failing test**

Create `news-radar/tests/test_filename_dates.py`:

```python
"""Tests for newsradar.filename_dates."""

import unittest
from datetime import date

from newsradar.filename_dates import parse_date_from_stem


class TestParseDateFromStem(unittest.TestCase):
    def test_parses_valid_stem(self):
        result = parse_date_from_stem("ai-radar-2026-05-21", "ai-radar")
        self.assertEqual(result, date(2026, 5, 21))

    def test_parses_robotics_prefix(self):
        result = parse_date_from_stem("robotics-radar-2026-01-03", "robotics-radar")
        self.assertEqual(result, date(2026, 1, 3))

    def test_returns_none_for_unparseable_suffix(self):
        result = parse_date_from_stem("ai-radar-latest", "ai-radar")
        self.assertIsNone(result)

    def test_returns_none_for_too_few_parts(self):
        result = parse_date_from_stem("ai-radar-2026-05", "ai-radar")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/keithfry/projects/news-radar && uv run pytest tests/test_filename_dates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'newsradar.filename_dates'`

- [ ] **Step 3: Write minimal implementation**

Create `news-radar/src/newsradar/filename_dates.py`:

```python
"""Shared filename-date parsing for radar episode files.

Episode files are named "<prefix>-YYYY-MM-DD" (e.g. "ai-radar-2026-05-21").
This is the single place that regex lives — podcast_rss.py and retention.py
both parse dates the same way.
"""

from datetime import date


def parse_date_from_stem(stem: str, prefix: str) -> date | None:
    """Parse YYYY-MM-DD out of a stem like 'ai-radar-2026-05-21'. None if unparseable."""
    suffix = stem[len(prefix):]
    parts = suffix.lstrip("-").split("-")
    if len(parts) >= 3:
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            return date(year, month, day)
        except (ValueError, IndexError):
            pass
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/keithfry/projects/news-radar && uv run pytest tests/test_filename_dates.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Refactor podcast_rss.py to use the shared helper**

In `news-radar/src/newsradar/podcast_rss.py`, add the import near the top (after the existing `from .topics import Topic` line):

```python
from .filename_dates import parse_date_from_stem
```

Replace the body of `_date_from_stem` (lines 35-45) with:

```python
def _date_from_stem(stem: str, prefix: str) -> datetime | None:
    """Parse YYYY-MM-DD from stem like 'ai-radar-2026-05-21' or 'robotics-radar-2026-05-21'."""
    parsed = parse_date_from_stem(stem, prefix)
    if parsed is None:
        return None
    return datetime(parsed.year, parsed.month, parsed.day, 8, 0, 0, tzinfo=timezone.utc)
```

- [ ] **Step 6: Run the existing podcast_rss tests to verify the refactor didn't break anything**

Run: `cd /Users/keithfry/projects/news-radar && uv run pytest tests/test_podcast_rss.py -v`
Expected: PASS (6 tests, same as before the refactor)

- [ ] **Step 7: Commit**

```bash
cd /Users/keithfry/projects/news-radar
git add src/newsradar/filename_dates.py src/newsradar/podcast_rss.py tests/test_filename_dates.py
git commit -m "Extract shared filename-date parsing helper"
```

---

### Task 2: Retention purge logic

**Files:**
- Create: `news-radar/src/newsradar/retention.py`
- Test: `news-radar/tests/test_retention.py`

**Interfaces:**
- Consumes: `parse_date_from_stem(stem: str, prefix: str) -> date | None` (Task 1)
- Produces:
  - `purge_audio(output_dir: Path, file_prefix: str, max_age_days: int, now: datetime, log=print) -> list[Path]`
  - `purge_episodes(output_dir: Path, file_prefix: str, max_age_days: int, now: datetime, log=print) -> list[Path]`

  Both take a topic's output directory (e.g. `techradar/AI`) laid out as `output_dir/YYYY-MM/<prefix>-YYYY-MM-DD.<ext>`, same layout `podcast_rss.py` and the main pipeline already use. Both return every path they deleted or modified — Task 4's orchestrator uses this list for the git-add and the summary printout.

- [ ] **Step 1: Write the failing tests**

Create `news-radar/tests/test_retention.py`:

```python
"""Tests for newsradar.retention purge logic."""

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from newsradar.retention import purge_audio, purge_episodes

_AUDIO_EXTS = (".mp3", ".chapters.json", ".transcript.json", ".jpg", ".og.jpg")

_PLAYER_HTML = (
    '<div class="page-header">\n'
    '  <div class="header-stats">\n'
    '  </div>\n'
    '  <div class="podcast-player">\n'
    '    <audio controls preload="none" src="https://example.com/ai-radar-2026-01-01.mp3">'
    'Your browser does not support audio.</audio>\n'
    '  <a class="podcast-subscribe" href="https://example.com/podcast.rss">🎙 Subscribe</a>\n'
    '  </div>\n'
    '</div>\n'
)

_OG_META = (
    '<meta property="og:title" content="AI Daily Digest — January 1, 2026"/>\n'
    '<meta property="og:description" content="AI news digest — January 1, 2026"/>\n'
    '<meta property="og:image" content="https://example.com/ai-radar-2026-01-01.og.jpg"/>\n'
    '<meta property="og:image:width" content="1200"/>\n'
    '<meta property="og:image:height" content="630"/>\n'
    '<meta property="og:type" content="website"/>\n'
    '<meta name="twitter:card" content="summary_large_image"/>\n'
    '<meta name="twitter:image" content="https://example.com/ai-radar-2026-01-01.og.jpg"/>\n'
)


def _write_episode(month_dir: Path, date_str: str, prefix: str = "ai-radar", with_html: bool = True) -> None:
    month_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{prefix}-{date_str}"
    for ext in _AUDIO_EXTS:
        (month_dir / f"{stem}{ext}").write_bytes(b"x")
    (month_dir / f"{stem}.json").write_text("{}")
    if with_html:
        html = f"<html>\n<head>\n{_OG_META}</head>\n<body>\n{_PLAYER_HTML}</body>\n</html>\n"
        (month_dir / f"{stem}.html").write_text(html)


class TestPurgeAudio(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.output_dir = Path(self.tmp.name)
        self.now = datetime(2026, 6, 1, tzinfo=timezone.utc)  # "today" for all tests

    def tearDown(self):
        self.tmp.cleanup()

    def test_purges_audio_files_older_than_max_age(self):
        # 2026-01-01 is 151 days before 2026-06-01 — well past the 90-day threshold.
        _write_episode(self.output_dir / "2026-01", "2026-01-01")

        changed = purge_audio(self.output_dir, "ai-radar", 90, self.now)

        stem_dir = self.output_dir / "2026-01"
        for ext in _AUDIO_EXTS:
            self.assertFalse((stem_dir / f"ai-radar-2026-01-01{ext}").exists(), f"{ext} should be deleted")
        self.assertTrue((stem_dir / "ai-radar-2026-01-01.json").exists(), "json must survive")
        self.assertTrue((stem_dir / "ai-radar-2026-01-01.html").exists(), "html must survive")
        self.assertEqual(len(changed), len(_AUDIO_EXTS) + 1)  # 5 deleted files + 1 modified html

    def test_keeps_audio_files_within_max_age(self):
        # 2026-05-15 is 17 days before 2026-06-01 — inside the 90-day window.
        _write_episode(self.output_dir / "2026-05", "2026-05-15")

        changed = purge_audio(self.output_dir, "ai-radar", 90, self.now)

        stem_dir = self.output_dir / "2026-05"
        for ext in _AUDIO_EXTS:
            self.assertTrue((stem_dir / f"ai-radar-2026-05-15{ext}").exists())
        self.assertEqual(changed, [])

    def test_strips_player_and_og_meta_from_html(self):
        _write_episode(self.output_dir / "2026-01", "2026-01-01")

        purge_audio(self.output_dir, "ai-radar", 90, self.now)

        html = (self.output_dir / "2026-01" / "ai-radar-2026-01-01.html").read_text()
        self.assertNotIn("podcast-player", html)
        self.assertNotIn("og:image", html)
        self.assertNotIn("twitter:image", html)
        self.assertIn("<html>", html)  # rest of the page survives

    def test_idempotent_on_second_run(self):
        _write_episode(self.output_dir / "2026-01", "2026-01-01")
        purge_audio(self.output_dir, "ai-radar", 90, self.now)

        changed = purge_audio(self.output_dir, "ai-radar", 90, self.now)

        self.assertEqual(changed, [])  # nothing left to delete or strip

    def test_boundary_exactly_at_max_age_is_not_purged(self):
        # 2026-03-03 is exactly 90 days before 2026-06-01.
        _write_episode(self.output_dir / "2026-03", "2026-03-03")

        changed = purge_audio(self.output_dir, "ai-radar", 90, self.now)

        self.assertEqual(changed, [])


class TestPurgeEpisodes(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.output_dir = Path(self.tmp.name)
        self.now = datetime(2026, 6, 1, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def test_purges_all_files_older_than_max_age_and_removes_empty_dir(self):
        # 2026-01-01 is 151 days before 2026-06-01 — past the 150-day threshold.
        month_dir = self.output_dir / "2026-01"
        _write_episode(month_dir, "2026-01-01")

        changed = purge_episodes(self.output_dir, "ai-radar", 150, self.now)

        self.assertFalse(month_dir.exists(), "empty month dir should be removed")
        self.assertEqual(len(changed), len(_AUDIO_EXTS) + 2)  # 5 audio + .json + .html

    def test_keeps_dir_when_another_episode_still_present(self):
        month_dir = self.output_dir / "2026-01"
        _write_episode(month_dir, "2026-01-01")  # 151 days old — purged
        _write_episode(month_dir, "2026-01-31")  # 121 days old — kept

        purge_episodes(self.output_dir, "ai-radar", 150, self.now)

        self.assertTrue(month_dir.exists())
        self.assertFalse((month_dir / "ai-radar-2026-01-01.json").exists())
        self.assertTrue((month_dir / "ai-radar-2026-01-31.json").exists())

    def test_keeps_files_within_max_age(self):
        month_dir = self.output_dir / "2026-05"
        _write_episode(month_dir, "2026-05-15")  # 17 days old

        changed = purge_episodes(self.output_dir, "ai-radar", 150, self.now)

        self.assertEqual(changed, [])
        self.assertTrue(month_dir.exists())

    def test_purges_episode_with_audio_already_purged(self):
        # Simulates an episode that already went through purge_audio: only
        # html + json remain, both must still be caught by purge_episodes.
        month_dir = self.output_dir / "2026-01"
        _write_episode(month_dir, "2026-01-01")
        for ext in _AUDIO_EXTS:
            (month_dir / f"ai-radar-2026-01-01{ext}").unlink()

        changed = purge_episodes(self.output_dir, "ai-radar", 150, self.now)

        self.assertFalse(month_dir.exists())
        self.assertEqual(len(changed), 2)  # .json + .html


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/keithfry/projects/news-radar && uv run pytest tests/test_retention.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'newsradar.retention'`

- [ ] **Step 3: Write the implementation**

Create `news-radar/src/newsradar/retention.py`:

```python
"""Retention: purge old radar episodes from a topic's output directory.

Two tiers, both keyed off the date encoded in an episode's filename stem
(not file mtime — mtimes get touched by backfills and git operations, the
filename date is the authoritative "episode date"):

  - purge_audio: drops audio-only artifacts (mp3, chapters, transcript,
    cover images) once an episode crosses its max_age_days. If the
    episode's HTML page survives, strips the inline podcast player and
    og:image/twitter:image meta tags so it doesn't point at now-deleted
    files.
  - purge_episodes: drops everything left for an episode once it crosses
    its own (larger) max_age_days, and removes the YYYY-MM directory if
    that leaves it empty.

Both operate on a single topic's output_dir, laid out as
output_dir/YYYY-MM/<file_prefix>-YYYY-MM-DD.<ext> — the same layout
podcast_rss.py and the main pipeline already use.
"""

import re
from datetime import date, datetime
from pathlib import Path

from .filename_dates import parse_date_from_stem

_YM_DIR_RE = re.compile(r"^\d{4}-\d{2}$")

_AUDIO_EXTS = (".mp3", ".chapters.json", ".transcript.json", ".jpg", ".og.jpg")

_PLAYER_RE = re.compile(r'\n?\s*<div class="podcast-player">.*?</div>\n?', re.DOTALL)
_OG_META_RE = re.compile(
    r'<meta property="og:title".*?<meta name="twitter:image"[^>]*/>\n',
    re.DOTALL,
)


def _episode_stems(output_dir: Path, file_prefix: str) -> list[tuple[Path, date, str]]:
    """Return (month_dir, episode_date, stem) for every dated episode found under output_dir."""
    results: list[tuple[Path, date, str]] = []
    if not output_dir.is_dir():
        return results

    stem_re = re.compile(rf"^{re.escape(file_prefix)}-(\d{{4}}-\d{{2}}-\d{{2}})")
    for month_dir in sorted(output_dir.iterdir()):
        if not month_dir.is_dir() or not _YM_DIR_RE.match(month_dir.name):
            continue
        seen: set[str] = set()
        for f in sorted(month_dir.iterdir()):
            match = stem_re.match(f.name)
            if not match:
                continue
            date_str = match.group(1)
            if date_str in seen:
                continue
            seen.add(date_str)
            ep_date = parse_date_from_stem(f"{file_prefix}-{date_str}", file_prefix)
            if ep_date is not None:
                results.append((month_dir, ep_date, f"{file_prefix}-{date_str}"))
    return results


def _strip_audio_references(html_path: Path, log=print) -> bool:
    """Remove the inline podcast player and og:image/twitter:image meta tags.

    Returns True if the file was modified (False if there was nothing to strip,
    e.g. a second run against an already-stripped file).
    """
    text = html_path.read_text(encoding="utf-8")
    new_text = _PLAYER_RE.sub("\n", text)
    new_text = _OG_META_RE.sub("", new_text)
    if new_text == text:
        return False
    html_path.write_text(new_text, encoding="utf-8")
    log(f"    stripped audio references: {html_path}")
    return True


def purge_audio(
    output_dir: Path, file_prefix: str, max_age_days: int, now: datetime, log=print
) -> list[Path]:
    """Delete audio artifacts for episodes older than max_age_days. HTML/JSON survive. Returns changed paths."""
    changed: list[Path] = []
    for month_dir, ep_date, stem in _episode_stems(output_dir, file_prefix):
        if (now.date() - ep_date).days <= max_age_days:
            continue

        for ext in _AUDIO_EXTS:
            f = month_dir / f"{stem}{ext}"
            if f.exists():
                f.unlink()
                log(f"    deleted: {f}")
                changed.append(f)

        html_path = month_dir / f"{stem}.html"
        if html_path.exists() and _strip_audio_references(html_path, log=log):
            changed.append(html_path)

    return changed


def purge_episodes(
    output_dir: Path, file_prefix: str, max_age_days: int, now: datetime, log=print
) -> list[Path]:
    """Delete every remaining file for episodes older than max_age_days.

    Removes the YYYY-MM directory if it ends up empty. Returns changed paths.
    """
    changed: list[Path] = []
    touched_dirs: set[Path] = set()

    for month_dir, ep_date, stem in _episode_stems(output_dir, file_prefix):
        if (now.date() - ep_date).days <= max_age_days:
            continue

        for f in sorted(month_dir.glob(f"{stem}*")):
            f.unlink()
            log(f"    deleted: {f}")
            changed.append(f)
        touched_dirs.add(month_dir)

    for month_dir in touched_dirs:
        if month_dir.is_dir() and not any(month_dir.iterdir()):
            month_dir.rmdir()
            log(f"    removed empty dir: {month_dir}")

    return changed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/keithfry/projects/news-radar && uv run pytest tests/test_retention.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/keithfry/projects/news-radar
git add src/newsradar/retention.py tests/test_retention.py
git commit -m "Add retention purge logic for old radar episodes"
```

---

### Task 3: Rename `hooks/publish.py`'s `_run` to a reusable `run_git`

**Files:**
- Modify: `techradar/hooks/publish.py` (whole file — renames `_run` to `run_git`, no behavior change)

**Interfaces:**
- Produces: `run_git(repo_root: Path, args: list[str], check: bool = True, log=print) -> subprocess.CompletedProcess` — same signature as the old `_run`, just public so Task 4's `retention.py` can import it without reaching into a private name.

This repo has no test suite (confirmed: `find techradar -iname "*test*"` turns up nothing) — `run.py` and `hooks/publish.py` are both validated by manual runs today, so this task's validation step is the same: a manual smoke check, not a new pytest run.

- [ ] **Step 1: Rename every occurrence**

In `techradar/hooks/publish.py`, rename the function definition and all 5 call sites from `_run` to `run_git`. The function body is unchanged — only the name.

```python
def run_git(repo_root: Path, args: list[str], check: bool = True, log=print) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True, cwd=repo_root)
    if result.stdout.strip():
        log(f"  [git] {result.stdout.strip()}")
    if result.stderr.strip():
        log(f"  [git] {result.stderr.strip()}")
    if check and result.returncode != 0:
        raise RuntimeError(f"git command failed: {' '.join(args)}\n{result.stderr}")
    return result
```

And update the 5 call sites inside `publish_hook` (the ones currently reading `_run(repo_root, [...], ...)`) to `run_git(repo_root, [...], ...)`.

- [ ] **Step 2: Verify the rename is complete**

Run: `grep -n "_run(" techradar/hooks/publish.py`
Expected: no matches (everything renamed to `run_git`)

Run: `grep -n "def run_git\|run_git(" techradar/hooks/publish.py`
Expected: 1 definition + 5 call sites, all using `run_git`

- [ ] **Step 3: Commit**

```bash
cd /Users/keithfry/projects/techradar
git add hooks/publish.py
git commit -m "Rename publish.py's _run to run_git so retention.py can reuse it"
```

---

### Task 4: `techradar/retention.py` orchestrator script

**Files:**
- Create: `techradar/retention.py`

**Interfaces:**
- Consumes:
  - `newsradar.config.load_config(path: str | Path) -> Config` (existing)
  - `newsradar.podcast_rss.generate_podcast_rss(output_dir, topic, base_url, author_name, output_dir_rel, log=print) -> Path` (existing)
  - `newsradar.retention.purge_audio(output_dir, file_prefix, max_age_days, now, log=print) -> list[Path]` (Task 2)
  - `newsradar.retention.purge_episodes(output_dir, file_prefix, max_age_days, now, log=print) -> list[Path]` (Task 2)
  - `hooks.publish.run_git(repo_root, args, check=True, log=print) -> subprocess.CompletedProcess` (Task 3)
- Produces: a runnable script — no other file imports this one.

No automated tests for this task (matches `run.py`'s existing zero-test-coverage pattern in this repo) — validated in Task 6 by a manual dry-run against real data plus a manual full run against a scratch copy.

- [ ] **Step 1: Write the script**

Create `techradar/retention.py`:

```python
#!/usr/bin/env python3
"""Manually-run retention job: purges old AI/Robotics radar episodes.

    uv run retention.py --config config/config.toml [--dry-run]

Two tiers (see docs/superpowers/specs/2026-08-06-retention-job-design.md):
  - audio artifacts (mp3/chapters/transcript/covers) purged after 90 days
  - full episodes (html/json + any leftovers) purged after 150 days

Regenerates podcast.rss and index.html for anything touched, then commits
and pushes — unless --dry-run, which stops after regeneration so the
changes can be inspected with `git status`/`git diff` before committing
manually.
"""

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from newsradar.config import load_config
from newsradar.podcast_rss import generate_podcast_rss
from newsradar.retention import purge_audio, purge_episodes

from hooks.publish import run_git

AUDIO_MAX_AGE_DAYS = 90
EPISODE_MAX_AGE_DAYS = 150

GIT_USER_NAME = "Keith Fry"
GIT_USER_EMAIL = "keithfry@gmail.com"


def log(msg: str) -> None:
    print(msg, flush=True)


def _regenerate_index(repo_root: Path, touched_dirs: set[Path]) -> list[Path]:
    """Delete stale index.html under touched dirs (+ the repo-root techradar/ index,
    which lists the topic dirs) and rebuild via generate-index.sh. Returns rewritten index paths.
    """
    top_dir = repo_root / "techradar"
    all_dirs = set(touched_dirs) | {top_dir}

    for output_dir in all_dirs:
        index_path = output_dir / "index.html"
        if index_path.exists():
            index_path.unlink()

    rel_dirs = [str(d.relative_to(repo_root)) for d in sorted(all_dirs)]
    result = subprocess.run(
        ["bash", str(repo_root / ".github" / "scripts" / "generate-index.sh"), *rel_dirs],
        capture_output=True, text=True, cwd=repo_root,
    )
    if result.stdout.strip():
        log(f"  {result.stdout.strip()}")
    if result.returncode != 0:
        log(f"  WARNING: generate-index.sh failed: {result.stderr.strip()}")
        return []

    return [d / "index.html" for d in all_dirs if (d / "index.html").exists()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to config.toml")
    parser.add_argument("--dry-run", action="store_true", help="Skip the final git commit/push")
    args = parser.parse_args()

    config = load_config(args.config)
    repo_root = config.repo_root.parent
    now = datetime.now(timezone.utc)

    all_changed: list[Path] = []
    touched_dirs: set[Path] = set()
    summary: list[str] = []

    for topic in config.topics.values():
        output_dir = config.output_root / topic.output_dir
        log(f"── {topic.display_name} ──")

        audio_changed = purge_audio(output_dir, topic.file_prefix, AUDIO_MAX_AGE_DAYS, now, log=log)
        episode_changed = purge_episodes(output_dir, topic.file_prefix, EPISODE_MAX_AGE_DAYS, now, log=log)
        changed = audio_changed + episode_changed
        all_changed.extend(changed)
        if changed:
            touched_dirs.add(output_dir)

        summary.append(
            f"{topic.display_name}: {len(audio_changed)} audio file(s) purged, "
            f"{len(episode_changed)} episode file(s) purged"
        )

        rss_output_dir_rel = (
            f"{config.site.public_path_prefix}/{topic.output_dir}"
            if config.site.public_path_prefix else topic.output_dir
        )
        rss_path = generate_podcast_rss(
            output_dir=output_dir,
            topic=topic,
            base_url=config.site.base_url,
            author_name=config.site.author_name,
            output_dir_rel=rss_output_dir_rel,
            log=log,
        )
        all_changed.append(rss_path)

    if touched_dirs:
        log("Regenerating index.html...")
        all_changed.extend(_regenerate_index(repo_root, touched_dirs))

    log("")
    log("=== Retention summary ===")
    for line in summary:
        log(f"  {line}")

    if not all_changed:
        log("Nothing changed, skipping commit.")
        return

    if args.dry_run:
        log(f"--dry-run: {len(all_changed)} path(s) changed, skipping commit/push. Review with git status/diff.")
        return

    lock = repo_root / ".git" / "index.lock"
    if lock.exists():
        lock.unlink()
        log("  removed stale .git/index.lock")

    run_git(repo_root, ["git", "-C", str(repo_root), "pull", "--rebase", "--autostash"], log=log)

    for path in all_changed:
        rel = path.relative_to(repo_root)
        run_git(repo_root, ["git", "-C", str(repo_root), "add", "--", str(rel)], log=log)

    date_str = now.strftime("%Y-%m-%d")
    commit_lines = "\n".join(f"- {line}" for line in summary)
    commit_msg = f"Retention: prune old AI/Robotics radar files ({date_str})\n\n{commit_lines}"

    result = run_git(
        repo_root,
        [
            "git", "-C", str(repo_root),
            "-c", f"user.name={GIT_USER_NAME}",
            "-c", f"user.email={GIT_USER_EMAIL}",
            "commit", "-m", commit_msg,
        ],
        check=False,
        log=log,
    )
    if result.returncode != 0:
        if "nothing to commit" in result.stdout + result.stderr:
            log("  nothing to commit, skipping push")
            return
        raise RuntimeError(f"git commit failed:\n{result.stderr}")

    run_git(repo_root, ["git", "-C", str(repo_root), "push"], log=log)
    log(f"  pushed: {commit_msg.splitlines()[0]}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make it executable and verify it parses**

```bash
cd /Users/keithfry/projects/techradar
chmod +x retention.py
source .venv/bin/activate
python3 -c "import ast; ast.parse(open('retention.py').read())"
python3 retention.py --help
```
Expected: `--help` prints the usage/description without error.

- [ ] **Step 3: Commit**

```bash
cd /Users/keithfry/projects/techradar
git add retention.py
git commit -m "Add retention.py orchestrator script"
```

---

### Task 5: `techradar/retention-agent.sh` wrapper

**Files:**
- Create: `techradar/retention-agent.sh`

**Interfaces:**
- Consumes: `techradar/retention.py` (Task 4) via `uv run`
- Produces: a runnable wrapper — nothing else depends on it.

- [ ] **Step 1: Write the script**

Create `techradar/retention-agent.sh`:

```bash
#!/bin/bash
# Manual wrapper for retention.py — mirrors run-agent.sh's launchd-safe
# log-filename stamping, but this one's meant to be run by hand:
#   ./retention-agent.sh              # purge + regenerate + commit + push
#   ./retention-agent.sh --dry-run    # purge + regenerate only, no commit/push
set -euo pipefail

cd /Users/keithfry/projects/techradar
mkdir -p logs

LOG_FILE="logs/techradar-retention-$(date +%Y-%m-%d).log"

exec /opt/homebrew/bin/uv run retention.py --config config/config.toml "$@" >>"$LOG_FILE" 2>&1
```

- [ ] **Step 2: Make it executable**

```bash
cd /Users/keithfry/projects/techradar
chmod +x retention-agent.sh
```

- [ ] **Step 3: Verify permissions**

Run: `ls -l retention-agent.sh`
Expected: permissions include `x` (e.g. `-rwxr-xr-x`)

- [ ] **Step 4: Commit**

```bash
cd /Users/keithfry/projects/techradar
git add retention-agent.sh
git commit -m "Add retention-agent.sh wrapper"
```

---

### Task 6: Manual acceptance run

**Files:** none created/modified — this is a verification-only task.

**Interfaces:** none — exercises Tasks 1-5 end to end against real data.

- [ ] **Step 1: Dry-run against the real repo**

```bash
cd /Users/keithfry/projects/techradar
./retention-agent.sh --dry-run
tail -60 logs/techradar-retention-$(date +%Y-%m-%d).log
```

Confirm the log shows per-topic purge counts and, if anything was old enough to purge, a "Regenerating index.html..." line — with no commit/push lines (dry-run stops before those).

- [ ] **Step 2: Inspect what actually changed on disk**

```bash
git status
git diff --stat
```

Confirm: any deleted files are audio artifacts (mp3/chapters/transcript/jpg/og.jpg) from episodes older than 90 days, or full episode files from episodes older than 150 days — nothing recent got touched. If `git diff` shows a modified `.html` file, confirm the podcast player and og:image tags are gone but the rest of the article content is intact (`git diff path/to/that.html`).

- [ ] **Step 3: Revert the dry-run's disk changes before doing a real run**

Since this was a dry run intended only to verify behavior, discard it before deciding whether to do a real run:

```bash
git checkout -- .
git clean -fd techradar/
```

- [ ] **Step 4: Decide on a real run**

If step 2's inspection looked correct, either wait for enough episodes to actually age past the thresholds, or run `./retention-agent.sh` (no `--dry-run`) when ready. This step has no fixed pass/fail — it's a judgment call by the person running the job, not part of the automated implementation.
