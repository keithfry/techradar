# Retention job design

Date: 2026-08-06

## Problem

`techradar/AI` and `techradar/Robotics` accumulate one episode's worth of
files every weekday and never delete anything. This grows the repo (and
Pages build) unboundedly. We want a manually-triggered job that prunes old
content.

**What gets purged and when — the two-tier rules and the 90/150-day default
thresholds — is a core `newsradar` requirement, specified in the `news-radar`
repo: `news-radar/docs/plans/2026-08-06-retention-design.md`.** (Moved there
2026-09-20 so other sites built on `newsradar` share it.) This doc covers
only the techradar-specific job that calls that logic and publishes the
result.

## Components

### 1. `newsradar.retention` (in the `news-radar` repo)

`purge_audio`, `purge_episodes`, and the `DEFAULT_AUDIO_MAX_AGE_DAYS` /
`DEFAULT_EPISODE_MAX_AGE_DAYS` constants. See the news-radar design doc.

### 2. `techradar/retention.py` (new script, sibling to `run.py`)

Thin orchestrator, run manually:

```
uv run retention.py --config config/config.toml [--dry-run]
```

1. Load `Config` the same way `run.py` does.
   `now` is local time, not UTC — filename dates are local, and a UTC
   "today" would purge a day early every evening. `--audio-days` /
   `--episode-days` override the newsradar defaults (for testing).
2. For each topic in `config.topics.values()`:
   - `changed += purge_audio(output_dir, topic.file_prefix, DEFAULT_AUDIO_MAX_AGE_DAYS, now, log)`
   - `changed += purge_episodes(output_dir, topic.file_prefix, DEFAULT_EPISODE_MAX_AGE_DAYS, now, log)`
3. For each topic that had a change: remove any `YYYY-MM` directory whose
   only remaining file is its generated `index.html` (`purge_episodes` only
   removes truly empty dirs), then regenerate `podcast.rss` via the existing
   `newsradar.podcast_rss.generate_podcast_rss` — it globs mp3s fresh off
   disk, so purged episodes fall out with no manual list-editing. Untouched
   topics are skipped: the feed carries a `lastBuildDate`, so regenerating
   one would produce a no-op commit every run.
4. Delete every `index.html` under each touched topic dir — month dirs
   included, their indexes carry the mp3 badges (the generate-index.sh "skip
   if up to date" check only looks at file mtimes newer than the index, which
   a deletion doesn't produce — so forcing regen by removing the stale index
   first is required), then run `.github/scripts/generate-index.sh` for the
   touched topic dirs. Output is deterministic, so untouched months come back
   byte-identical.
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

- If `generate-index.sh` exits non-zero, log a warning and continue (same
  behavior as `hooks/publish.py` today) rather than aborting the whole job
  — an index regen failure shouldn't block the file deletions that already
  happened.
- If the final git commit fails because there's nothing to commit (e.g. a
  no-op dry run followed immediately by a real run with nothing new to
  prune), log and exit 0 rather than raising.

## Testing

- Purge logic is unit-tested in `news-radar` (see its design doc).
- Manual dry-run against the real `techradar/AI` and `techradar/Robotics`
  trees as the acceptance check before the first real (non-dry-run) run.

## Out of scope

- No scheduling (cron/launchd) — user runs this manually.
