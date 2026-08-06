# Retention job design

Date: 2026-08-06

## Problem

`techradar/AI` and `techradar/Robotics` accumulate one episode's worth of
files every weekday (`.mp3`, `.chapters.json`, `.transcript.json`, `.jpg`,
`.og.jpg`, `.html`, `.json`) and never delete anything. This grows the repo
(and Pages build) unboundedly. We want a manually-triggered job that prunes
old content on two timers:

- **3 months (90 days)**: purge audio-related artifacts — mp3, chapters,
  transcript, cover images. Keep the episode's HTML article page and JSON
  data alive.
- **5 months (150 days)**: purge everything left for that episode — HTML,
  JSON, and any leftover audio files (covers backfilled/edge-case episodes
  where audio purge didn't already run). Remove the `YYYY-MM` directory if
  it ends up empty.

Age is computed from the date embedded in the filename (e.g.
`ai-radar-2026-05-01`), not file mtime — mtimes get touched by backfills and
git operations; the filename date is the authoritative "episode date."

## Components

### 1. `news-radar/src/newsradar/retention.py` (new module)

Pure, reusable purge logic — no git, no CLI, just filesystem + HTML edits.
Reuses the filename-date regex already in `podcast_rss._date_from_stem`
(promoted to a shared helper both modules import, to avoid duplicating it).

- `purge_audio(output_dir: Path, file_prefix: str, max_age_days: int, now: datetime, log=print) -> list[Path]`
  For each dated episode older than `max_age_days`:
  - Delete `.mp3`, `.chapters.json`, `.transcript.json`, `.jpg`, `.og.jpg`
    if present.
  - If the episode's `.html` exists, strip the inline podcast player block
    (`_podcast_player_html`'s output — the `<div class="podcast-player">…
    </div>`, matched structurally) and the `og:image`/`twitter:image` meta
    lines. Idempotent — if already stripped (e.g. rerunning the job), no-op.
  - Returns every path deleted or modified, for the git-add list and the
    summary printout.

- `purge_episodes(output_dir: Path, file_prefix: str, max_age_days: int, now: datetime, log=print) -> list[Path]`
  For each dated episode older than `max_age_days`: delete every remaining
  file for that date stem (`.html`, `.json`, and any audio files that
  survived because `purge_audio` hadn't run on them yet). After processing
  a `YYYY-MM` directory, remove it if empty. Returns deleted paths.

Both functions are per-topic-output-dir (caller loops topics), and both
take `now` as a parameter rather than calling `datetime.now()` internally,
so they're deterministic and testable.

### 2. `techradar/retention.py` (new script, sibling to `run.py`)

Thin orchestrator, run manually:

```
uv run retention.py --config config/config.toml [--dry-run]
```

1. Load `Config` the same way `run.py` does.
2. For each topic in `config.topics.values()`:
   - `changed += purge_audio(output_dir, topic.file_prefix, 90, now, log)`
   - `changed += purge_episodes(output_dir, topic.file_prefix, 150, now, log)`
3. For each topic, regenerate `podcast.rss` via the existing
   `newsradar.podcast_rss.generate_podcast_rss` — it globs mp3s fresh off
   disk, so purged episodes fall out with no manual list-editing.
4. Delete existing `index.html` files under every directory that had a
   change (the generate-index.sh "skip if up to date" check only looks at
   file mtimes newer than the index, which a deletion doesn't produce — so
   forcing regen by removing the stale index first is required), then run
   `.github/scripts/generate-index.sh` for the affected topic dirs (and the
   repo-root `techradar/` index, since it lists top-level topic dirs too).
5. Print a summary: episodes purged (audio-only vs full) and files deleted,
   per topic.
6. **Unless `--dry-run`**: git add all changed/deleted paths (using `git add -A`
   scoped to the affected topic dirs plus regenerated index/rss files),
   commit (`Retention: prune old AI/Robotics radar files (2026-08-06)`,
   listing per-topic counts in the body), push. Reuses the git-command
   subprocess pattern already in `hooks/publish.py` (pull --rebase
   --autostash, add, commit, push), factored so both call a shared helper
   rather than duplicating the subprocess plumbing.

   With `--dry-run`, steps 1-5 still run (files really get deleted/edited
   on disk, so `git status`/`git diff` shows the real effect) — only the
   commit+push at the end is skipped, so the user can inspect and either
   commit manually or rerun without the flag.

### 3. `techradar/retention-agent.sh` (new script, sibling to `run-agent.sh`)

Same launchd-wrapper shape as `run-agent.sh` — stamps a dated log filename
(since launchd plists can't use strftime) and execs the real script — but
passes through arguments so `--dry-run` (or any future flag) reaches
`retention.py`:

```bash
#!/bin/bash
set -euo pipefail
cd /Users/keithfry/projects/techradar
mkdir -p logs
LOG_FILE="logs/techradar-retention-$(date +%Y-%m-%d).log"
exec /opt/homebrew/bin/uv run retention.py --config config/config.toml "$@" >>"$LOG_FILE" 2>&1
```

Run manually, e.g.:
```
./retention-agent.sh --dry-run
./retention-agent.sh
```

## Error handling

- Missing files (already deleted, or a file that never existed for an
  episode) are treated as no-ops, not errors — `Path.unlink(missing_ok=True)`.
- If `generate-index.sh` exits non-zero, log a warning and continue (same
  behavior as `hooks/publish.py` today) rather than aborting the whole job
  — an index regen failure shouldn't block the file deletions that already
  happened.
- If the final git commit fails because there's nothing to commit (e.g. a
  no-op dry run followed immediately by a real run with nothing new to
  prune), log and exit 0 rather than raising.

## Testing

- Unit tests for `purge_audio`/`purge_episodes` against a temp directory
  seeded with fake dated episode files at various ages, asserting which
  files survive/are deleted and that HTML stripping is idempotent.
- Manual dry-run against the real `techradar/AI` and `techradar/Robotics`
  trees as the acceptance check before the first real (non-dry-run) run.

## Out of scope

- No change to `MAX_EPISODES = 20` cap in `podcast_rss.py` — that's a
  separate, already-existing limit on RSS feed size, unrelated to on-disk
  retention.
- No scheduling (cron/launchd) — user runs this manually.
